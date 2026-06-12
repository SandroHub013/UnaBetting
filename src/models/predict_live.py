
import pandas as pd
import numpy as np
import joblib
import yaml
from pathlib import Path
from src.features.player_stats import PlayerStatsEngine
from src.features.elo import EloRating
from src.features.sota_features import map_cpi

from src.runtime_paths import DATA_ROOT as PROJECT_ROOT  # writable+seeded root (repo root in dev)

def load_resources():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    scaler_path = PROJECT_ROOT / config["paths"]["models"] / "atp_scaler.pkl"
    features_meta_path = PROJECT_ROOT / config["paths"]["models"] / "atp_features.txt"
    medians_path = PROJECT_ROOT / config["paths"]["models"] / "atp_medians.pkl"
    
    scaler = joblib.load(scaler_path)
    medians = joblib.load(medians_path) if medians_path.exists() else {}
    
    with open(features_meta_path, "r") as f:
        feature_cols = [line.strip() for line in f if line.strip()]
        
    return config, scaler, feature_cols, medians

def get_player_id(name, df):
    """Try to find player ID from name."""
    match = df[df['winner_name'].str.contains(name, case=False, na=False)]
    if not match.empty:
        return match.iloc[0]['winner_id']
    match = df[df['loser_name'].str.contains(name, case=False, na=False)]
    if not match.empty:
        return match.iloc[0]['loser_id']
    return None

def predict_match(p1_name, p2_name, tourney_name, surface, tourney_level, odds_p1=None, odds_p2=None):
    config, scaler, feature_cols, medians = load_resources()
    
    # Load historical data to populate the engine
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df = pd.read_csv(unified_path, low_memory=False)
    
    # CRITICAL: Parse dates
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])
    df = df.sort_values('tourney_date')
    
    p1_id = get_player_id(p1_name, df)
    p2_id = get_player_id(p2_name, df)
    
    print(f"\n🔍 Analisi Match: {p1_name} (ID: {p1_id}) vs {p2_name} (ID: {p2_id})")
    
    # Initialize engines with historical data
    elo_engine = EloRating()
    stats_engine = PlayerStatsEngine(windows=(10, 20, 50))
    
    # This is a bit slow for a live script, in a real prod app we'd save the state
    print("  ⏳ Popolamento motori statistici (può richiedere un minuto)...")
    elo_engine.process_matches(df)
    
    # For stats engine, we need to record matches
    for _, row in df.iterrows():
        stats_engine.record_match(row, is_winner=True)
        stats_engine.record_match(row, is_winner=False)
        
    # Get features for today
    match_date = pd.Timestamp.now()
    p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date) if p1_id else {}
    p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date) if p2_id else {}
    
    # Build the feature vector
    input_data = {}
    
    # Prefix mapping (w_ for p1, l_ for p2)
    for k, v in p1_feats.items(): input_data[f"w_{k}"] = v
    for k, v in p2_feats.items(): input_data[f"l_{k}"] = v
    
    # Differences
    for k in p1_feats:
        if k in p2_feats:
            input_data[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)
            
    # ELO
    if p1_id and p2_id:
        w_elo = elo_engine.global_ratings[p1_id]
        l_elo = elo_engine.global_ratings[p2_id]
        w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
        l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
        
        input_data["w_elo"] = w_elo
        input_data["l_elo"] = l_elo
        input_data["w_surface_elo"] = w_s_elo
        input_data["l_surface_elo"] = l_s_elo
        input_data["elo_win_prob"] = elo_engine.expected_score(w_s_elo, l_s_elo)
    else:
        input_data["elo_win_prob"] = 0.5 # Baseline
        
    # Implied Prob
    if odds_p1 and odds_p2:
        margin = (1.0/odds_p1) + (1.0/odds_p2)
        input_data["w_implied_prob"] = (1.0/odds_p1) / margin
        input_data["l_implied_prob"] = (1.0/odds_p2) / margin
        input_data["diff_implied_prob"] = input_data["w_implied_prob"] - input_data["l_implied_prob"]
        input_data["has_odds"] = 1
        segment = "odds"
    else:
        input_data["w_implied_prob"] = 0
        input_data["l_implied_prob"] = 0
        input_data["diff_implied_prob"] = 0
        input_data["has_odds"] = 0
        segment = "blind"
    
    # CPI
    input_data["cpi"] = map_cpi(tourney_name, surface)
    
    # Context (Simplified for live)
    level_map = {'G': 'level_G', 'M': 'level_M', 'A': 'level_A'}
    for l_key in ['level_G', 'level_M', 'level_A', 'level_C', 'level_S', 'level_F', 'level_D']:
        input_data[l_key] = 1 if level_map.get(tourney_level) == l_key else 0
        
    # Create DataFrame and align columns
    X_live = pd.DataFrame([input_data])
    for col in feature_cols:
        if col not in X_live.columns:
            X_live[col] = 0 # Default for missing features
            
    X_live = X_live[feature_cols]
    
    # CRITICAL: Fill NaNs with training medians, not 0
    for col in feature_cols:
        if col in X_live.columns and pd.isna(X_live.at[0, col]):
            X_live.at[0, col] = medians.get(col, 0.5 if 'rate' in col or 'pct' in col or 'prob' in col else 0)
    
    # Load model
    model_path = PROJECT_ROOT / config["paths"]["models"] / f"atp_target_{segment}_ensemble.pkl"
    if not model_path.exists():
        print(f"❌ Errore: Modello {segment} non trovato in {model_path}")
        return
        
    model_data = joblib.load(model_path)
    model = model_data["model"] if isinstance(model_data, dict) and "model" in model_data else model_data
    
    # Scale and Predict
    X_scaled = scaler.transform(X_live)
    prob_p1 = model.predict_proba(X_scaled)[0, 1]
    prob_p2 = 1 - prob_p1
    
    print("\n" + "="*40)
    print(f"🎯 PREDIZIONE: {p1_name} vs {p2_name}")
    print("="*40)
    print(f"📊 Probabilità {p1_name}: {prob_p1:.2%}")
    print(f"📊 Probabilità {p2_name}: {prob_p2:.2%}")
    
    if odds_p1 and odds_p2:
        # Value detection
        fair_odds_p1 = 1.0 / prob_p1
        fair_odds_p2 = 1.0 / prob_p2
        
        print(f"\n💰 Quote Bet365: {odds_p1} / {odds_p2}")
        print(f"📉 Quote Fair:   {fair_odds_p1:.2f} / {fair_odds_p2:.2f}")
        
        if odds_p1 > fair_odds_p1:
            edge = (odds_p1 / fair_odds_p1) - 1
            print(f"✅ VALUE BET su {p1_name}! (Edge: {edge:.2%})")
        elif odds_p2 > fair_odds_p2:
            edge = (odds_p2 / fair_odds_p2) - 1
            print(f"✅ VALUE BET su {p2_name}! (Edge: {edge:.2%})")
        else:
            print("❌ Nessun valore trovato.")
    else:
        print(f"\n📊 Nessuna quota fornita. Modello utilizzato: {segment.upper()}")

if __name__ == "__main__":
    # Test con i dati estratti dall'utente
    predict_match(
        p1_name="Learner Tien", 
        p2_name="Davidovich Fokina", 
        tourney_name="Indian Wells Masters",
        surface="Hard",
        tourney_level="M",
        odds_p1=2.37,
        odds_p2=1.57
    )
