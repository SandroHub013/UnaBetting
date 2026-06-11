import pandas as pd
import numpy as np

def parse_pbp_match(match_row):
    """
    Parses a single point-by-point match record to extract clutch metrics.
    Returns a dictionary of stats for player1 (server1) and player2 (server2).
    """
    p1 = match_row['server1']
    p2 = match_row['server2']
    
    pbp_string = str(match_row['pbp'])
    if pbp_string == 'nan':
        return None
    
    # We want to track:
    # 1. Total Break Points Faced & Saved
    # 2. Total Break Points Created & Converted
    # 3. Total Deuce Points Played & Won
    # 4. Total Tiebreaks Played & Won
    
    stats = {
        p1: {'bp_saved': 0, 'bp_faced': 0, 'bp_converted': 0, 'bp_created': 0, 'deuce_won': 0, 'deuce_played': 0, 'tb_won': 0, 'tb_played': 0},
        p2: {'bp_saved': 0, 'bp_faced': 0, 'bp_converted': 0, 'bp_created': 0, 'deuce_won': 0, 'deuce_played': 0, 'tb_won': 0, 'tb_played': 0}
    }
    
    sets = pbp_string.split('.')
    current_server = 1  # 1 means p1 is serving, 2 means p2 is serving
    
    for set_idx, set_str in enumerate(sets):
        games = set_str.split(';')
        
        for game_idx, game_str in enumerate(games):
            if '/' in game_str:
                # Tiebreak
                # Only care about tiebreak winner. The winner of the tiebreak wins the last point.
                if len(game_str) > 0:
                    last_char = game_str.replace('/', '')[-1]
                    if last_char in ('S', 'A'):
                        tb_winner = p1 if current_server == 1 else p2
                    elif last_char in ('R', 'D'):
                        tb_winner = p2 if current_server == 1 else p1
                    else:
                        continue
                        
                    stats[p1]['tb_played'] += 1
                    stats[p2]['tb_played'] += 1
                    stats[tb_winner]['tb_won'] += 1
                    
                # Change server for the next set
                # In a tiebreak, the player who receives first serves the first game of the next set.
                current_server = 3 - current_server 
                continue
                
            # Regular game
            s_pts = 0
            r_pts = 0
            
            for pt in game_str:
                server_name = p1 if current_server == 1 else p2
                returner_name = p2 if current_server == 1 else p1
                
                # Check for break point before point is played
                # Break point: returner has >= 3 points and returner_points >= server_points + 1
                is_bp = (r_pts >= 3) and (r_pts >= s_pts + 1)
                
                # Check for deuce point (both have >=3 points, and are tied)
                is_deuce = (s_pts >= 3 and r_pts >= 3 and s_pts == r_pts)
                
                if pt in ('S', 'A'):
                    # Server won the point
                    if is_bp:
                        stats[server_name]['bp_faced'] += 1
                        stats[server_name]['bp_saved'] += 1
                        stats[returner_name]['bp_created'] += 1
                        # not converted
                        
                    if is_deuce:
                        stats[server_name]['deuce_played'] += 1
                        stats[server_name]['deuce_won'] += 1
                        stats[returner_name]['deuce_played'] += 1
                        
                    s_pts += 1
                    
                elif pt in ('R', 'D'):
                    # Returner won the point
                    if is_bp:
                        stats[server_name]['bp_faced'] += 1
                        stats[returner_name]['bp_created'] += 1
                        stats[returner_name]['bp_converted'] += 1
                        # not saved
                        
                    if is_deuce:
                        stats[server_name]['deuce_played'] += 1
                        stats[returner_name]['deuce_played'] += 1
                        stats[returner_name]['deuce_won'] += 1
                        
                    r_pts += 1
            
            # Change server for the next game
            current_server = 3 - current_server

    return stats

if __name__ == "__main__":
    df = pd.read_csv('data/raw/sackmann/tennis_pointbypoint/pbp_matches_atp_main_archive.csv', nrows=10)
    for idx, row in df.iterrows():
        print(f"Match: {row['server1']} vs {row['server2']}")
        print(f"PBP: {row['pbp']}")
        stats = parse_pbp_match(row)
        print(stats)
        print("-" * 50)
