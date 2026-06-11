import pandas as pd
import numpy as np

# Load unified data (the raw history)
unified = pd.read_csv('G:/tennis betting/data/processed/atp_unified.csv', low_memory=False)
unified['tourney_date'] = pd.to_datetime(unified['tourney_date'])
unified = unified.sort_values(['tourney_date', 'match_num'])

# Load features (the engineered data)
features = pd.read_csv('G:/tennis betting/data/features/atp_features.csv', low_memory=False)
features['tourney_date'] = pd.to_datetime(features['tourney_date'])

# Focus on Novak Djokovic (ID 104925)
djoko_id = 104925

# Get Djokovic's real history from unified data
djoko_unified = unified[(unified['winner_id'] == djoko_id) | (unified['loser_id'] == djoko_id)].copy()
djoko_unified['won'] = djoko_unified['winner_id'] == djoko_id

print(f"--- NOVAK DJOKOVIC HISTORY TRACE (ID {djoko_id}) ---")

# Let's pick a match in 2023
target_matches = djoko_unified[djoko_unified['tourney_date'].dt.year == 2023]

for i in range(len(target_matches)):
    match = target_matches.iloc[i]
    m_date = match['tourney_date']
    m_num = match['match_num']
    
    # Identify this match in the features file
    # (Matches in features should align with unified if sorted the same)
    feat_row = features[
        (features['tourney_date'] == m_date) & 
        (features['winner_id'] == match['winner_id']) & 
        (features['loser_id'] == match['loser_id'])
    ]
    
    if feat_row.empty:
        continue
        
    feat_row = feat_row.iloc[0]
    
    # Calculate PRE-MATCH win rate manually from unified data
    # We must look at matches strictly before this one
    past_matches = djoko_unified[
        (djoko_unified['tourney_date'] < m_date) | 
        ((djoko_unified['tourney_date'] == m_date) & (djoko_unified['match_num'] < m_num))
    ]
    
    recent_10 = past_matches.tail(10)
    manual_win_rate_10 = recent_10['won'].mean() if not recent_10.empty else np.nan
    
    # Get the feature value
    # If Djokovic is winner, we look at w_win_rate_10. If loser, l_win_rate_10.
    prefix = 'w' if match['winner_id'] == djoko_id else 'l'
    calculated_win_rate_10 = feat_row.get(f'{prefix}_win_rate_10')
    
    print(f"\nMatch {i+1}: {match['tourney_name']} ({m_date.date()}) vs {match['loser_name'] if match['won'] else match['winner_name']}")
    print(f"  Result: {'WIN' if match['won'] else 'LOSS'}")
    print(f"  Manual Pre-Match Win Rate (10): {manual_win_rate_10:.4f}")
    print(f"  Feature File Win Rate (10):    {calculated_win_rate_10:.4f}")
    
    if abs(manual_win_rate_10 - calculated_win_rate_10) > 1e-5:
        print("  ❌ DISCREPANCY DETECTED! Rolling stat is incorrect.")
    else:
        print("  ✅ MATCH! Rolling stat is correct for this match.")

    if i >= 4: # Just check first 5 matches of 2023
        break
