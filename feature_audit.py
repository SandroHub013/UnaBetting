import pandas as pd
import numpy as np

def run_feature_audit(tour="atp"):
    print(f"\n--- FEATURE QUALITY AUDIT: {tour.upper()} ---")
    path = f"G:/tennis betting/data/features/{tour}_features.csv"
    df = pd.read_csv(path, low_memory=False)
    
    # 1. Perspective Randomization Check
    # If target is randomized, the mean of 'diff_' features should be near 0
    diff_cols = [c for c in df.columns if c.startswith('diff_')]
    if diff_cols:
        means = df[diff_cols].mean()
        extreme_means = means[abs(means) > 0.1]
        print(f"1. Randomization Symmetry: {len(extreme_means)}/{len(diff_cols)} diff features have non-zero means (>0.1).")
        if not extreme_means.empty:
            print(f"   ⚠ Potential Bias found in: {extreme_means.index.tolist()[:5]}...")

    # 2. Duplicate Check (Look-ahead)
    # Check if any match (identified by date/ids) appears twice in the features
    id_cols = ['tourney_date', 'winner_id', 'loser_id']
    dups = df.duplicated(subset=id_cols, keep=False).sum()
    print(f"2. Feature Duplicates: {dups} rows")

    # 3. Value Range Sanity
    # Win rates should be between 0 and 1
    wr_cols = [c for c in df.columns if 'win_rate' in c]
    if wr_cols:
        invalid_wr = ((df[wr_cols] < 0) | (df[wr_cols] > 1)).sum().sum()
        print(f"3. Win Rate Sanity: {invalid_wr} values outside [0, 1]")

    # 4. ELO Sanity
    elo_cols = [c for c in df.columns if 'elo' in c and 'prob' not in c]
    if elo_cols:
        print(f"4. ELO Range: {df[elo_cols].min().min():.0f} to {df[elo_cols].max().max():.0f}")

    # 5. The "Smell Test" - Specific Row Trace
    # Let's look at one player's progression
    player_id = df['winner_id'].iloc[len(df)//2]
    p_matches = df[(df['winner_id'] == player_id) | (df['loser_id'] == player_id)].sort_values('tourney_date')
    print(f"\n5. Sample Player Trace (ID {player_id}):")
    trace_cols = ['tourney_date', 'target'] + ([c for c in df.columns if 'win_rate_10' in c][:2])
    print(p_matches[trace_cols].head(5))

if __name__ == "__main__":
    run_feature_audit("atp")
