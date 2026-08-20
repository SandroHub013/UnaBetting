import joblib
import pandas as pd
import numpy as np
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


def _fill_from_medians(X, feature_cols, medians):
    for col in feature_cols:
        if col in X.columns and not pd.isna(X.at[0, col]):
            continue
        if col in medians:
            X.at[0, col] = medians[col]
        else:
            X.at[0, col] = 0.5 if "prob" in col or "rate" in col else 0
    return X


def _scaled(X, feature_cols, scaler):
    return np.clip(scaler.transform(X[feature_cols]), -4, 4)


def _next_match_date():
    """Three days after the newest match in the unified dataset."""
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df_hist = pd.read_csv(unified_path, usecols=["tourney_date"])
    df_hist["tourney_date"] = pd.to_datetime(df_hist["tourney_date"], errors="coerce")
    return df_hist["tourney_date"].max() + pd.Timedelta(days=3)


def _report_importances(model, feature_cols, x_fixed, x_scaled_fixed):
    feats_imp = sorted(zip(feature_cols, model.feature_importances_),
                       key=lambda x: x[1], reverse=True)
    print("\n--- TOP XGBOOST FEATURES ---")
    for f, imp in feats_imp[:20]:
        try:
            z = x_scaled_fixed[0, feature_cols.index(f)]
        except (ValueError, IndexError):
            print(f"  {f:<22} NOT FOUND")
            continue
        print(f"  {f:<22}: Importance={imp:.4f} | Val={x_fixed.at[0, f]} | Z={z:.2f}")


def debug_tien_sinner():
    elo_engine, stats_engine, model, scaler, feature_cols = _load_artifacts()
    medians = joblib.load(PROJECT_ROOT / "models" / "atp_medians.pkl")

    # P1: Learner Tien (T0HA), P2: Jannik Sinner (S0AG)
    p1_id, p2_id, surface = "T0HA", "S0AG", "Hard"

    input_data = _player_block(stats_engine, p1_id, p2_id, surface, _next_match_date())
    input_data.update(_elo_block(elo_engine, p1_id, p2_id, surface))
    input_data.update(_odds_block(9.5, 1.06))
    input_data.update(_level_block())

    X = _fill_from_medians(pd.DataFrame([input_data]), feature_cols, medians)
    prob_base = model.predict_proba(_scaled(X, feature_cols, scaler))[0, 1]
    print(f"\nBASE PREDICTION [Tien vs Sinner] P1 Prob: {prob_base:.4f}")

    # TEST: fix Sinner's inactivity
    x_fixed = X.copy()
    x_fixed.at[0, "l_days_since_last"] = 3
    x_fixed.at[0, "diff_days_since_last"] = (x_fixed.at[0, "w_days_since_last"] or 7) - 3
    x_scaled_fixed = _scaled(x_fixed, feature_cols, scaler)

    prob_fixed = model.predict_proba(x_scaled_fixed)[0, 1]
    print(f"FIXED PREDICTION (After fixing Sinner inactivity) P1 Prob: {prob_fixed:.4f}")
    _report_importances(model, feature_cols, x_fixed, x_scaled_fixed)

if __name__ == "__main__":
    debug_tien_sinner()
