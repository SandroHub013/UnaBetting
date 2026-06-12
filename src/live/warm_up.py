import pandas as pd
import joblib
import yaml
from pathlib import Path
from src.features.player_stats import PlayerStatsEngine
from src.features.elo import EloRating

from src.runtime_paths import DATA_ROOT as PROJECT_ROOT  # writable+seeded root (repo root in dev)

def warm_up():
    print("🎾 Pre-calcolando i motori ELO e Statistiche per l'analisi LIVE...")
    
    # 1. Load config
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    output_dir = PROJECT_ROOT / "models"
    output_dir.mkdir(exist_ok=True)
    
    for tour in ["atp", "wta"]:
        print(f"\n[{tour.upper()}] Avvio warmup...")
        # 2. Load unified dataset
        unified_path = PROJECT_ROOT / "data" / "processed" / f"{tour}_unified.csv"
        if not unified_path.exists():
            print(f"❌ Errore: Dataset unificato non trovato in {unified_path}")
            continue
            
        df = pd.read_csv(unified_path, low_memory=False)
        df['tourney_date'] = pd.to_datetime(df['tourney_date'])
        df = df.sort_values('tourney_date')
        
        # 3. Initialize engines
        elo_engine = EloRating()
        stats_engine = PlayerStatsEngine(windows=(10, 20, 50))
        
        # 4. Process all historical matches
        print(f"  ⏳ Elaborazione di {len(df):,} match storici...")
        
        # Elo engine processes internally
        elo_engine.process_matches(df)
        
        # Stats engine needs manual record for now (matching build_features logic)
        for _, row in df.iterrows():
            stats_engine.record_match(row, is_winner=True)
            stats_engine.record_match(row, is_winner=False)
            
        # 5. Save the state
        cache_path = output_dir / f"{tour}_live_engines.pkl"
        state = {
            "elo": elo_engine,
            "stats": stats_engine,
            "last_update": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        joblib.dump(state, cache_path)
        print(f"✅ Motori salvati correttamente in {cache_path}")
        print(f"  - Giocatori mappati: {len(elo_engine.global_ratings):,}")

if __name__ == "__main__":
    warm_up()
