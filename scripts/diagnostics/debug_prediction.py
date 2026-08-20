import joblib
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path("g:/tennis betting")

def _load_artifacts(tour="atp"):
    """Live engines, model, scaler and the feature order they were trained on."""
    state = joblib.load(PROJECT_ROOT / "models" / f"{tour}_live_engines.pkl")
    model = joblib.load(PROJECT_ROOT / "models" / f"{tour}_target_lightgbm.pkl")
    scaler = joblib.load(PROJECT_ROOT / "models" / f"{tour}_scaler.pkl")
    with open(PROJECT_ROOT / "models" / f"{tour}_features.txt", "r") as f:
        feature_cols = [line.strip() for line in f if line.strip()]
    return state["elo"], state["stats"], model, scaler, feature_cols


def _player_block(stats_engine, p1_id, p2_id, surface, match_date):
    """w_ / l_ / diff_ features for one head-to-head."""
    p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date)
    p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date)
    block = {}
    for k, v in p1_feats.items():
        block[f"w_{k}"] = v
    for k, v in p2_feats.items():
        block[f"l_{k}"] = v
    for k in p1_feats:
        if k in p2_feats:
            block[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)
    return block


def _elo_block(elo_engine, p1_id, p2_id, surface):
    w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
    l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
    return {
        "w_elo": elo_engine.global_ratings[p1_id],
        "l_elo": elo_engine.global_ratings[p2_id],
        "w_surface_elo": w_s_elo,
        "l_surface_elo": l_s_elo,
        "elo_win_prob": elo_engine.expected_score(w_s_elo, l_s_elo),
    }


def _odds_block(o1, o2):
    margin = (1.0 / o1) + (1.0 / o2)
    w = (1.0 / o1) / margin
    l = (1.0 / o2) / margin
    return {"w_implied_prob": w, "l_implied_prob": l, "diff_implied_prob": w - l}


def _level_block(level="level_M"):
    keys = ["level_G", "level_M", "level_A", "level_C", "level_S", "level_F", "level_D"]
    return {k: int(k == level) for k in keys}


def _fill_defaults(input_data, feature_cols):
    """0.5 for anything rate-like, 0 otherwise — good enough for a smoke check."""
    rate_like = ("pct", "win_rate", "win_prob", "prob_")
    for col in feature_cols:
        if col not in input_data or input_data[col] is None:
            input_data[col] = 0.5 if any(x in col for x in rate_like) else 0
    return input_data


def _report_outliers(x_scaled, feature_cols, input_data):
    print("\n--- OUTLIER DETECTION (Z-SCORES) ---")
    feat_series = pd.Series(x_scaled[0], index=feature_cols)
    outliers = feat_series[feat_series.abs() > 3].sort_values(key=abs, ascending=False)
    for f, z in outliers.items():
        print(f"  {f:<22}: Z={z:.2f} (Value: {input_data.get(f, 'N/A')})")


def debug_full_match():
    elo_engine, stats_engine, model, scaler, feature_cols = _load_artifacts()

    # P1: Alcaraz (A0E2), P2: Ruud (RH16)
    p1_id, p2_id, surface = "A0E2", "RH16", "Hard"

    input_data = _player_block(stats_engine, p1_id, p2_id, surface, pd.Timestamp.now())
    input_data.update(_elo_block(elo_engine, p1_id, p2_id, surface))
    input_data.update(_odds_block(1.09, 9.05))  # real prices from the user report
    input_data["cpi"] = 35
    input_data.update(_level_block())
    _fill_defaults(input_data, feature_cols)

    # TEST: override staleness
    input_data["w_days_since_last"] = 3
    input_data["l_days_since_last"] = 3
    input_data["diff_days_since_last"] = 0

    X = pd.DataFrame([input_data])[feature_cols].fillna(0)

    print("\n--- TOP RAW FEATURES for Alcaraz vs Ruud ---")
    problem_feats = ["w_days_since_last", "l_days_since_last", "diff_days_since_last",
                     "w_n_matches_surface", "l_n_matches_surface", "w_h2h", "l_h2h"]
    for f in problem_feats:
        if f in input_data:
            print(f"  {f:<22}: {input_data[f]}")

    x_scaled = scaler.transform(X)
    print(f"\nFINAL PREDICTION PROB P1: {model.predict_proba(x_scaled)[0, 1]:.4f}")
    _report_outliers(x_scaled, feature_cols, input_data)

if __name__ == "__main__":
    debug_full_match()
