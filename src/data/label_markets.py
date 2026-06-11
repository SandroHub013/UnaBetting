import pandas as pd
import re
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def parse_score(score_str):
    """
    Parses a tennis score string like '6-4 3-6 7-6(5)' or '6-0 6-0' 
    into (winner_games, loser_games, total_games, game_diff).
    """
    if pd.isna(score_str) or not isinstance(score_str, str):
        return 0, 0, 0, 0
    
    # Remove retirements, walkovers, etc.
    if any(x in score_str.upper() for x in ["RET", "W/O", "DEF", "ABN"]):
        return np.nan, np.nan, np.nan, np.nan

    # Regex to find game scores (handles tiebreak scores in parens)
    # Match pattern like 6-4 or 7-6(5)
    pattern = re.compile(r'(\d+)-(\d+)(?:\(\d+\))?')
    sets = pattern.findall(score_str)
    
    w_games = 0
    l_games = 0
    
    for s in sets:
        try:
            w_games += int(s[0])
            l_games += int(s[1])
        except (ValueError, IndexError):
            continue
            
    if w_games == 0 and l_games == 0:
        return np.nan, np.nan, np.nan, np.nan
        
    return w_games, l_games, w_games + l_games, w_games - l_games

def label_dataset(tour="atp"):
    input_path = PROJECT_ROOT / "data" / "processed" / f"{tour}_unified.csv"
    output_path = PROJECT_ROOT / "data" / "processed" / f"{tour}_market_labeled.csv"
    
    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path, low_memory=False)
    
    print("Labeling markets (Spreads & Totals)...")
    labels = df['score'].apply(parse_score)
    
    df[['winner_games', 'loser_games', 'total_games', 'game_diff']] = pd.DataFrame(labels.tolist(), index=df.index)
    
    # Drop rows where parsing failed (retirements, etc.)
    df_clean = df.dropna(subset=['total_games']).copy()
    
    print(f"Saving labeled dataset to {output_path}...")
    df_clean.to_csv(output_path, index=False)
    print(f"Done. Processed {len(df_clean)} complete matches out of {len(df)}.")

if __name__ == "__main__":
    label_dataset("atp")
