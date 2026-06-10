import joblib
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path("g:/tennis betting")

def debug_tien_sinner():
    # Load resources
    cache_path = PROJECT_ROOT / "models" / "live_engines.pkl"
    state = joblib.load(cache_path)
    elo_engine = state['elo']
    stats_engine = state['stats']
    
    # Models
    model = joblib.load(PROJECT_ROOT / "models" / "atp_target_lightgbm.pkl")
    scaler = joblib.load(PROJECT_ROOT / "models" / "atp_scaler.pkl")
    with open(PROJECT_ROOT / "models" / "atp_features.txt", "r") as f:
        feature_cols = [line.strip() for line in f if line.strip()]
    
    medians = joblib.load(PROJECT_ROOT / "models" / "atp_medians.pkl")

    # P1: Learner Tien (T0HA), P2: Jannik Sinner (S0AG)
    p1_id = "T0HA"
    p2_id = "S0AG"
    surface = "Hard"
    
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df_hist = pd.read_csv(unified_path, usecols=['tourney_date'])
    df_hist['tourney_date'] = pd.to_datetime(df_hist['tourney_date'], errors='coerce')
    last_db_date = df_hist['tourney_date'].max()
    match_date = last_db_date + pd.Timedelta(days=3)
    
    p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date)
    p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date)
    
    input_data = {}
    for k, v in p1_feats.items(): input_data[f"w_{k}"] = v
    for k, v in p2_feats.items(): input_data[f"l_{k}"] = v
    for k in p1_feats:
        if k in p2_feats:
            input_data[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)
            
    # ELO
    w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
    l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
    input_data["w_elo"] = elo_engine.global_ratings[p1_id]
    input_data["l_elo"] = elo_engine.global_ratings[p2_id]
    input_data["w_surface_elo"] = w_s_elo
    input_data["l_surface_elo"] = l_s_elo
    input_data["elo_win_prob"] = elo_engine.expected_score(w_s_elo, l_s_elo)
    
    # Odds
    o1, o2 = 9.5, 1.06
    margin = (1.0/o1) + (1.0/o2)
    input_data["w_implied_prob"] = (1.0/o1) / margin
    input_data["l_implied_prob"] = (1.0/o2) / margin
    input_data["diff_implied_prob"] = input_data["w_implied_prob"] - input_data["l_implied_prob"]
    
    # Static
    for l_key in ['level_G', 'level_M', 'level_A', 'level_C', 'level_S', 'level_F', 'level_D']:
        input_data[l_key] = 1 if l_key == 'level_M' else 0

    X = pd.DataFrame([input_data])
    # Fill missing with medians
    for col in feature_cols:
        if col not in X.columns or pd.isna(X.at[0, col]):
            if col in medians:
                X.at[0, col] = medians[col]
            else:
                X.at[0, col] = 0.5 if "prob" in col or "rate" in col else 0
                
    # Initial Prediction
    X_pred = X[feature_cols]
    X_scaled = scaler.transform(X_pred)
    X_scaled = np.clip(X_scaled, -4, 4)
    prob_base = model.predict_proba(X_scaled)[0, 1]
    print(f"\nBASE PREDICTION [Tien vs Sinner] P1 Prob: {prob_base:.4f}")

    # TEST: Fix Sinner Inactivity
    X_fixed = X.copy()
    X_fixed.at[0, "l_days_since_last"] = 3
    X_fixed.at[0, "diff_days_since_last"] = (X_fixed.at[0, "w_days_since_last"] or 7) - 3

    X_pred_fixed = X_fixed[feature_cols]
    X_scaled_fixed = scaler.transform(X_pred_fixed)
    X_scaled_fixed = np.clip(X_scaled_fixed, -4, 4)
    
    prob_fixed = model.predict_proba(X_scaled_fixed)[0, 1]
    print(f"FIXED PREDICTION (After fixing Sinner inactivity) P1 Prob: {prob_fixed:.4f}")
    
    # Feature Importance for XGBoost
    importances = model.feature_importances_
    feats_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    print("\n--- TOP XGBOOST FEATURES ---")
    for f, imp in feats_imp[:20]:
        val = X_fixed.at[0, f]
        try:
            col_idx = feature_cols.index(f)
            z = X_scaled_fixed[0, col_idx]
            print(f"  {f:<22}: Importance={imp:.4f} | Val={val} | Z={z:.2f}")
        except:
            print(f"  {f:<22} NOT FOUND")

if __name__ == "__main__":
    debug_tien_sinner()
