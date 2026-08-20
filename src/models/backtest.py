"""Realistic backtest for the ATP winner model (2025+ out-of-sample).

Design pattern: the model only ever sees the feature matrix X (preprocessed
exactly like training: perspective randomization -> train medians -> scaler).
Real bookmaker odds (WITH vig) live in a separate aligned meta-frame and are
used exclusively for bet selection PnL — they never enter X.

Fixes vs the previous version:
- applies saved train medians + StandardScaler (predictions were degenerate
  without scaling: 95.6% of rows predicted "p1 wins")
- perspective-randomized inference (winner-POV rows leak the label: betting
  "p1" auto-wins by construction)
- bets against REAL B365 odds including margin, not de-vigged fair odds
- excludes rows whose implied probs are the 0.5/0.5 no-odds sentinel fill
- stake cap + Quarter Kelly; B365 is fixed-odds so no exchange commission
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.runtime_paths import DATA_ROOT as ROOT  # writable+seeded root (repo root in dev)

KELLY_FRACTION = 0.25
MIN_EDGE = 0.03
MAX_STAKE_PCT = 0.02      # max 2% of bankroll per bet
MIN_ODDS = 1.30           # skip super-favourites (Kelly variance trap)
STARTING_BANKROLL = 1000.0
SEED = 42   # MUST match train.prepare_training_data's randomization seed (42), so the
            # backtest reproduces the exact preprocessing the headline metrics were
            # measured on — no separate, drift-prone reimplementation.


def load_inference_inputs():
    features_path = ROOT / "data/features/atp_features.csv"
    if not features_path.exists():
        sys.exit(f"[X] Features not found: {features_path.relative_to(ROOT)}\n"
                 "    Build the pipeline first: python -m src.data.download && "
                 "python -m src.data.clean && python -m src.features.build_features")
    df = pd.read_csv(features_path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
    df = df[df["tourney_date"].dt.year >= 2025].sort_values("tourney_date")

    # real odds only — drop rows where implied probs are the 0.5 sentinel fill
    odds_w = pd.to_numeric(df["B365W"], errors="coerce").fillna(
        pd.to_numeric(df.get("PSW"), errors="coerce")).fillna(
        pd.to_numeric(df.get("AvgW"), errors="coerce"))
    odds_l = pd.to_numeric(df["B365L"], errors="coerce").fillna(
        pd.to_numeric(df.get("PSL"), errors="coerce")).fillna(
        pd.to_numeric(df.get("AvgL"), errors="coerce"))
    has_odds = odds_w.notna() & odds_l.notna() & (odds_w > 1.0) & (odds_l > 1.0)
    df = df[has_odds].copy()
    df["odds_w"], df["odds_l"] = odds_w[has_odds], odds_l[has_odds]
    return df


def predict_winner_prob(df, models_dir=None):
    """Return P(actual winner wins) per match — ORIENTATION-INVARIANT.

    The model is not perfectly perspective-symmetric, so a single random flip made
    the result (and the betting PnL) depend on the seed. We instead score each match
    in BOTH orientations and average: winner-POV gives P(winner wins); loser-POV gives
    P(loser wins), so 1 − that is also P(winner wins). The mean is deterministic,
    seed-free, and a fairer read of the model's true belief. Preprocessing reuses
    train.py's canonical randomizer (train medians -> scaler), not a hand-rolled copy.
    """
    base_dir = Path(models_dir) if models_dir else ROOT / "models"
    # E4 (2026-06-12): the odds-ensemble (market features, real-odds rows) is the
    # current headline model; falls back to the legacy single xgboost if absent.
    _odds = base_dir / "atp_target_odds_ensemble.pkl"
    model_path = _odds if _odds.exists() else base_dir / "atp_target_xgboost.pkl"
    scaler_path = base_dir / "atp_scaler.pkl"
    medians_path = base_dir / "atp_medians.pkl"
    missing = [p.relative_to(base_dir) for p in (model_path, scaler_path, medians_path)
               if not p.exists()]
    if missing:
        sys.exit("[X] Trained models not found: " + ", ".join(map(str, missing)) + "\n"
                 "    Train first: python -m src.models.train")
    model_data = joblib.load(model_path)
    model, features = model_data["model"], model_data["feature_cols"]
    scaler = joblib.load(scaler_path)
    medians = pd.Series(joblib.load(medians_path))

    # Preprocessing reuses train.py's canonical randomizer (train medians -> scaler),
    # not a hand-rolled copy. We score each match in BOTH orientations and average so
    # the result is deterministic and free of the model's perspective asymmetry.
    from src.models.train import _randomize_perspective
    base = df[features].copy()
    n = len(base)
    y_dummy = pd.DataFrame({"target": np.ones(n, dtype=int)}, index=base.index)

    def _prep(X):
        X = X.fillna(medians.reindex(features))
        return pd.DataFrame(scaler.transform(X), columns=features, index=X.index)

    # POV 1 — winner perspective (no flip): P(p1 == winner wins)
    p_win = model.predict_proba(_prep(base.copy()))[:, 1]
    # POV 2 — loser perspective (flip ALL rows): P(p1 == loser wins) -> winner = 1 - that
    flipped, _ = _randomize_perspective(base.copy(), y_dummy,
                                        flip_mask=np.ones(n, dtype=bool))
    p_lose = model.predict_proba(_prep(flipped))[:, 1]
    return (p_win + (1.0 - p_lose)) / 2.0  # orientation-invariant P(actual winner)


def _best_bet(row):
    """Highest-edge side of a match, or None when neither clears the filters.

    Edge is measured against the REAL price, so the bookmaker's vig is included.
    """
    p1, p2 = row["p_winner"], 1 - row["p_winner"]
    is_p1_fav = row["odds_w"] < row["odds_l"]
    cands = [(p1, row["odds_w"], True, is_p1_fav),
             (p2, row["odds_l"], False, not is_p1_fav)]
    best = None
    for p, odds, is_win, is_fav in cands:
        if odds < MIN_ODDS:
            continue
        edge = p - 1.0 / odds
        if edge > MIN_EDGE and (best is None or edge > best[-1]):
            best = (p, odds, is_win, is_fav, edge)
    if best is None:
        return None
    return best


def _kelly_stake(p, odds, bankroll):
    """Fractional Kelly stake, capped; None when the edge does not justify a bet."""
    b = odds - 1.0
    kelly = (p * b - (1 - p)) / b
    if kelly <= 0:
        return None
    return bankroll * min(kelly * KELLY_FRACTION, MAX_STAKE_PCT)


def _save_backtest_result(df, acc, n, wins, losses, profit, max_dd):
    """Headline numbers for the metrics-publish step, so it need not re-run this."""
    import json as _json
    from datetime import datetime as _dt

    res = {
        "ran_at": _dt.now().isoformat(timespec="seconds"),
        "matches": int(len(df)), "bets": n, "won": wins, "lost": losses,
        "win_rate": round(wins / n, 4) if n else None,
        "roi_pct": round(profit / STARTING_BANKROLL * 100, 1),
        "max_drawdown_pct": round(max_dd * 100, 1),
        "model_accuracy": round(float(acc), 4),
        "market_accuracy": round(float((df["odds_w"] < df["odds_l"]).mean()), 4),
    }
    out_p = ROOT / "reports" / "last_backtest.json"
    out_p.parent.mkdir(exist_ok=True)
    out_p.write_text(_json.dumps(res, indent=2), encoding="utf-8")
    print(f"[+] saved {out_p.relative_to(ROOT)}")


def run_backtest():
    print("=" * 60)
    print("  REALISTIC BACKTEST 2025+  (real B365 odds, vig included)")
    print("=" * 60)
    df = load_inference_inputs()
    print(f"[*] matches with real odds: {len(df)}")

    df["p_winner"] = predict_winner_prob(df)

    # model accuracy sanity (honest, perspective-neutral)
    acc = (df["p_winner"] > 0.5).mean()
    print(f"[*] model accuracy on these matches: {acc:.4f}")
    print(f"[*] B365 favourite accuracy:         "
          f"{(df['odds_w'] < df['odds_l']).mean():.4f}")

    bankroll = STARTING_BANKROLL
    peak, max_dd = bankroll, 0.0
    wins = losses = 0

    for _, row in df.iterrows():
        best = _best_bet(row)
        if best is None:
            continue
        p, odds, is_win = best[0], best[1], best[2]
        stake = _kelly_stake(p, odds, bankroll)
        if stake is None:
            continue
        b = odds - 1.0
        if is_win:
            bankroll += stake * b
            wins += 1
        else:
            bankroll -= stake
            losses += 1
        peak = max(peak, bankroll)
        max_dd = max(max_dd, (peak - bankroll) / peak)

    n = wins + losses
    profit = bankroll - STARTING_BANKROLL
    print("\n" + "=" * 60)
    print(f"  Quarter Kelly | edge>{MIN_EDGE:.0%} | stake cap {MAX_STAKE_PCT:.0%} | odds>={MIN_ODDS}")
    print("=" * 60)
    print(f"bets placed:   {n} / {len(df)} matches")
    print(f"won / lost:    {wins} / {losses}"
          + (f"  (win rate {wins / n:.1%})" if n else ""))
    print(f"final bankroll: EUR {bankroll:.2f}  (start {STARTING_BANKROLL:.0f})")
    print(f"net profit:     EUR {profit:.2f}  ROI {profit / STARTING_BANKROLL:.1%}")
    print(f"max drawdown:   {max_dd:.1%}")

    _save_backtest_result(df, acc, n, wins, losses, profit, max_dd)


def _bet_season(df_year):
    """One season of betting; returns wins, losses and the agree/disagree split."""
    bankroll = STARTING_BANKROLL
    wins = losses = 0
    agree_pnl = disagree_pnl = 0.0
    agree_bets = disagree_bets = 0

    for _, row in df_year.iterrows():
        best = _best_bet(row)
        if best is None:
            continue
        p, odds, is_win, is_fav = best[0], best[1], best[2], best[3]
        stake = _kelly_stake(p, odds, bankroll)
        if stake is None:
            continue
        b = odds - 1.0
        net_profit = stake * b if is_win else -stake
        bankroll += net_profit
        if is_win:
            wins += 1
        else:
            losses += 1
        if is_fav:
            agree_pnl += net_profit
            agree_bets += 1
        else:
            disagree_pnl += net_profit
            disagree_bets += 1

    return wins, losses, (agree_pnl, agree_bets), (disagree_pnl, disagree_bets)


def _print_walk_forward_summary(total_wins, total_losses, rois, agree, disagree):
    print("\n" + "=" * 60)
    print("  WALK-FORWARD SUMMARY")
    print("=" * 60)
    print(f"Total bets placed: {total_wins + total_losses}")
    print(f"Overall Won / Lost: {total_wins} / {total_losses}")
    if rois:
        print(f"ROI Distribution (per season): {np.mean(rois):.1%} ± {np.std(rois):.1%}")
    print("\nEdge Decomposition:")
    print(f"  Bets agreeing with market (backing fav): {agree[1]} | Net PnL: EUR {agree[0]:.2f}")
    print(f"  Bets disagreeing with market (backing dog): {disagree[1]} | Net PnL: EUR {disagree[0]:.2f}")
    print("=" * 60)


def run_walk_forward():
    print("=" * 60)
    print("  WALK-FORWARD BACKTEST (Rolling Training)")
    print("=" * 60)

    # Load all real-odds features
    features_path = ROOT / "data/features/atp_features.csv"
    if not features_path.exists():
        sys.exit("[X] Features not found")
    df = pd.read_csv(features_path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")

    odds_w = pd.to_numeric(df["B365W"], errors="coerce").fillna(pd.to_numeric(df.get("PSW"), errors="coerce")).fillna(pd.to_numeric(df.get("AvgW"), errors="coerce"))
    odds_l = pd.to_numeric(df["B365L"], errors="coerce").fillna(pd.to_numeric(df.get("PSL"), errors="coerce")).fillna(pd.to_numeric(df.get("AvgL"), errors="coerce"))
    has_odds = odds_w.notna() & odds_l.notna() & (odds_w > 1.0) & (odds_l > 1.0)

    df_eval = df[has_odds].copy()
    df_eval["odds_w"], df_eval["odds_l"] = odds_w[has_odds], odds_l[has_odds]

    from src.models.train import train_models
    import tempfile

    eval_years = [2023, 2024, 2025]
    total_wins = 0
    total_losses = 0
    rois = []

    # Track metrics separately for "agrees with market" vs "disagrees"
    # Market favourite is the one with lower odds.
    agree_pnl = 0.0
    agree_bets = 0
    disagree_pnl = 0.0
    disagree_bets = 0

    for year in eval_years:
        print(f"\n---> Training up to {year-1}, betting {year}...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            # validation years are skipped: train straight up to `year`
            train_models(tour="atp", target_col="target", save_dir=tmp_dir,
                         test_year=year, val_years=[])

            df_year = df_eval[df_eval["tourney_date"].dt.year == year].copy()
            if len(df_year) == 0:
                print(f"No matches with odds in {year}.")
                continue
            df_year["p_winner"] = predict_winner_prob(df_year, models_dir=tmp_dir)

            wins, losses, agree, disagree = _bet_season(df_year)
            agree_pnl += agree[0]
            agree_bets += agree[1]
            disagree_pnl += disagree[0]
            disagree_bets += disagree[1]

            n = wins + losses
            roi = (agree[0] + disagree[0]) / STARTING_BANKROLL
            rois.append(roi)
            total_wins += wins
            total_losses += losses
            print(f"    Bets: {n} | Won: {wins} | Lost: {losses} | ROI: {roi:.1%}")

    _print_walk_forward_summary(total_wins, total_losses, rois,
                                (agree_pnl, agree_bets), (disagree_pnl, disagree_bets))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--walk-forward", action="store_true", help="Run the rolling walk-forward backtest")
    args = parser.parse_args()

    run_backtest()
    if args.walk_forward:
        run_walk_forward()
