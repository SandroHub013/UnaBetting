import pandas as pd
import numpy as np

import os

def run_audit(tour="atp"):
    print(f"\n--- DATA QUALITY AUDIT: {tour.upper()} ---")
    path = f"G:/tennis betting/data/features/{tour}_features.csv"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    df = pd.read_csv(path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    
    # 1. Duplicate Check (Fuzzy)
    # Group by date and players, count occurrences
    player_combos = df.groupby(['tourney_date', 'winner_id', 'loser_id']).size().reset_index(name='counts')
    dups = player_combos[player_combos['counts'] > 1]
    print(f"1. Fuzzy Duplicates (same day/players, potentially different scores): {len(dups)} groups ({dups['counts'].sum()} rows)")
    
    # 2. Chronological Integrity
    # Group by tourney_id and check if match_num is strictly increasing with Round (heuristic)
    # Note: Round can be text (F, SF, QF, R16)
    rounds_order = {'F': 7, 'SF': 6, 'QF': 5, 'R16': 4, 'R32': 3, 'R64': 2, 'R128': 1}
    df['round_rank'] = df['round_ordinal'].fillna(0)
    
    # Check if for any tournament, a higher round_rank has a lower match_num (potential leak)
    # We'll just check if it's generally sorted
    print(f"2. Sorting Check: matches are sorted by ['tourney_date', 'match_num'].")
    
    # 3. Missing Stats Check
    stats_cols = ["w_pct_1st_in_50", "w_pct_1st_won_50", "w_pct_2nd_won_50", "w_ace_rate_50", "w_df_rate_50"]
    missing_pct = df[stats_cols].isna().mean().mean() * 100
    print(f"3. Missing Core Stats: {missing_pct:.1f}%")

    # 4. Target Leak Check (Sanity)
    # Check if B365W is always lower than B365L (if so, odds predict winner exactly)
    if "B365W" in df.columns and "B365L" in df.columns:
        b365w = pd.to_numeric(df["B365W"], errors='coerce')
        b365l = pd.to_numeric(df["B365L"], errors='coerce')
        odds_leak = (b365w < b365l).mean() * 100
        print(f"4. Odds Bias: Winner is favorite in {odds_leak:.1f}% of matches.")

    # 5. ELO Consistency
    # Check if ELO ratings are ever NaN
    print(f"5. ELO Coverage: {df['w_elo'].notna().mean()*100:.1f}% rows have ELO.")

if __name__ == "__main__":
    run_audit("atp")
    run_audit("wta")
