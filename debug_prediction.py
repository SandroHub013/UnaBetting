import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import os

PROJECT_ROOT = Path("g:/tennis betting")

def debug_full_match():
    # Load resources
    cache_path = PROJECT_ROOT / "models" / "live_engines.pkl"
    state = joblib.load(cache_path)
    elo_engine = state['elo']
    stats_engine = state['stats']
    
    model = joblib.load(PROJECT_ROOT / "models" / "atp_target_lightgbm.pkl")
    scaler = joblib.load(PROJECT_ROOT / "models" / "atp_scaler.pkl")
    with open(PROJECT_ROOT / "models" / "atp_features.txt", "r") as f:
        feature_cols = [line.strip() for line in f if line.strip()]

    # P1: Alcaraz (A0E2), P2: Ruud (RH16)
    p1_id = "A0E2"
    p2_id = "RH16"
    surface = "Hard"
    match_date = pd.Timestamp.now()
    
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
    
    # Odds (Real from user report)
    o1, o2 = 1.09, 9.05
    margin = (1.0/o1) + (1.0/o2)
    input_data["w_implied_prob"] = (1.0/o1) / margin
    input_data["l_implied_prob"] = (1.0/o2) / margin
    input_data["diff_implied_prob"] = input_data["w_implied_prob"] - input_data["l_implied_prob"]
    
    # Static
    input_data["cpi"] = 35
    for l_key in ['level_G', 'level_M', 'level_A', 'level_C', 'level_S', 'level_F', 'level_D']:
        input_data[l_key] = 1 if l_key == 'level_M' else 0

    # Fill missing with medians (0.5 for rates/probs is a safe guess for testing)
    for col in feature_cols:
        if col not in input_data or input_data[col] is None:
            if any(x in col for x in ["pct", "win_rate", "win_prob", "prob_"]):
                input_data[col] = 0.5
            else:
                input_data[col] = 0
                
    # TEST: Override staleness
    input_data["w_days_since_last"] = 3
    input_data["l_days_since_last"] = 3
    input_data["diff_days_since_last"] = 0

    X = pd.DataFrame([input_data])
    X = X[feature_cols].fillna(0)
    
    print("\n--- TOP RAW FEATURES for Alcaraz vs Ruud ---")
    # Debug specific features that might be problematic
    problem_feats = ["w_days_since_last", "l_days_since_last", "diff_days_since_last", 
                     "w_n_matches_surface", "l_n_matches_surface", "w_h2h", "l_h2h"]
    for f in problem_feats:
        if f in input_data:
            print(f"  {f:<22}: {input_data[f]}")

    X_scaled = scaler.transform(X)
    prob = model.predict_proba(X_scaled)[0, 1]
    
    print(f"\nFINAL PREDICTION PROB P1: {prob:.4f}")
    
    # Explain SHAP-style (feature contribution)
    # Since we don't have SHAP installed, we can check the scaled values vs mean
    print("\n--- OUTLIER DETECTION (Z-SCORES) ---")
    feat_series = pd.Series(X_scaled[0], index=feature_cols)
    outliers = feat_series[feat_series.abs() > 3].sort_values(key=abs, ascending=False)
    for f, z in outliers.items():
        print(f"  {f:<22}: Z={z:.2f} (Value: {input_data.get(f, 'N/A')})")

if __name__ == "__main__":
    debug_full_match()
