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


def predict_winner_prob(df):
    """Return P(actual winner wins) per match, via perspective-neutral inference."""
    # E4 (2026-06-12): the odds-ensemble (market features, real-odds rows) is the
    # current headline model; falls back to the legacy single xgboost if absent.
    _odds = ROOT / "models/atp_target_odds_ensemble.pkl"
    model_path = _odds if _odds.exists() else ROOT / "models/atp_target_xgboost.pkl"
    scaler_path = ROOT / "models/atp_scaler.pkl"
    medians_path = ROOT / "models/atp_medians.pkl"
    missing = [p.relative_to(ROOT) for p in (model_path, scaler_path, medians_path)
               if not p.exists()]
    if missing:
        sys.exit("[X] Trained models not found: " + ", ".join(map(str, missing)) + "\n"
                 "    Train first: python -m src.models.train")
    model_data = joblib.load(model_path)
    model, features = model_data["model"], model_data["feature_cols"]
    scaler = joblib.load(scaler_path)
    medians = pd.Series(joblib.load(medians_path))

    # Canonical preprocessing — reuse train.py's perspective randomizer instead of
    # a hand-rolled copy, so the backtest sees byte-for-byte the same inputs the
    # headline metrics were measured on (randomize @ seed 42 -> train medians -> scaler).
    from src.models.train import _randomize_perspective
    X = df[features].copy()
    # Raw rows are winner-POV (p1 == winner), so the pre-flip target is 1 everywhere;
    # the randomizer flips ~50% of rows and the target with them.
    y = pd.DataFrame({"target": np.ones(len(X), dtype=int)}, index=X.index)
    X, y = _randomize_perspective(X, y, seed=SEED)
    flip = y["target"].values == 0  # rows where p1 became the loser after the flip

    X = X.fillna(medians.reindex(features))
    X = pd.DataFrame(scaler.transform(X), columns=features, index=X.index)
    p1 = model.predict_proba(X)[:, 1]
    return np.where(flip, 1.0 - p1, p1)  # prob of the ACTUAL winner


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
    pnl = []

    for _, row in df.iterrows():
        # candidate bets: (model prob, odds, did it win)
        cands = [(row["p_winner"], row["odds_w"], True),
                 (1 - row["p_winner"], row["odds_l"], False)]
        best = None
        for p, odds, is_win in cands:
            if odds < MIN_ODDS:
                continue
            edge = p - 1.0 / odds  # vs REAL price (vig included)
            if edge > MIN_EDGE and (best is None or edge > best[3]):
                best = (p, odds, is_win, edge)
        if best is None:
            continue
        p, odds, is_win, edge = best
        b = odds - 1.0
        kelly = (p * b - (1 - p)) / b
        if kelly <= 0:
            continue
        stake = bankroll * min(kelly * KELLY_FRACTION, MAX_STAKE_PCT)
        if is_win:
            bankroll += stake * b
            wins += 1
        else:
            bankroll -= stake
            losses += 1
        pnl.append(bankroll)
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

    # Persist the headline backtest result so the metrics-publish step can read
    # the money number without re-running the backtest.
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


if __name__ == "__main__":
    run_backtest()
