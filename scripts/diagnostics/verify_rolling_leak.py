import pandas as pd
import numpy as np

# Load the features and the original unified data
features = pd.read_csv('G:/tennis betting/data/features/atp_features.csv', low_memory=False)
unified = pd.read_csv('G:/tennis betting/data/processed/atp_unified.csv', low_memory=False)

# Check a few matches where the "pre-match" stat might be identical to the "current match" stat
# We need to find the same matches in both. They should have the same order if concat worked.

print("Checking for identity between 'pre-match' rolling stats and 'current-match' stats...")

# For some matches, compare w_ace_rate_10 with (w_ace / w_svpt)
# Note: w_ace_rate_10 is in features, w_ace and w_svpt are in unified.

# Let's align them
match_keys = ['tourney_date', 'winner_name', 'loser_name']
merged = pd.concat([unified[match_keys + ['w_ace', 'w_svpt']], features[['w_ace_rate_10']]], axis=1)

merged['current_match_ace_rate'] = merged['w_ace'] / merged['w_svpt']

# Check how many are EXACTLY the same (to within epsilon)
# Since ace_rate_10 is an average of 10, it's unlikely to be exactly equal unless it's only 1 match.
merged = merged.dropna()
same = np.abs(merged['w_ace_rate_10'] - merged['current_match_ace_rate']) < 1e-6

print(f"Total matches checked: {len(merged)}")
print(f"Matches where rolling stats == current match stats: {same.sum()} ({same.mean()*100:.2f}%)")

# If it's 100%, we have a serious leak.
# If it's 10%, it might just be the first match for players.

# Let's check if the feature engine is "one off"
# Compare w_ace_rate_10 of match N with ace_rate of match N-1 for that player.
# That's harder to do here, but let's look at a few rows.
print("\nSample rows:")
print(merged[['w_ace_rate_10', 'current_match_ace_rate']].head(10))
