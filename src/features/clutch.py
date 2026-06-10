import pandas as pd
import numpy as np
from pathlib import Path
import glob
import yaml
from tqdm import tqdm

def parse_pbp_match(match_row):
    """
    Parses a single point-by-point match record to extract clutch metrics.
    Returns a dictionary of stats for player1 (server1) and player2 (server2).
    """
    p1 = match_row['server1']
    p2 = match_row['server2']
    
    pbp_string = str(match_row.get('pbp', 'nan'))
    if pbp_string == 'nan' or not pbp_string:
        return None
        
    stats = {
        p1: {'bp_saved': 0, 'bp_faced': 0, 'bp_converted': 0, 'bp_created': 0, 'deuce_won': 0, 'deuce_played': 0, 'tb_won': 0, 'tb_played': 0},
        p2: {'bp_saved': 0, 'bp_faced': 0, 'bp_converted': 0, 'bp_created': 0, 'deuce_won': 0, 'deuce_played': 0, 'tb_won': 0, 'tb_played': 0}
    }
    
    sets = pbp_string.split('.')
    current_server = 1  # 1 means p1 is serving, 2 means p2 is serving
    
    for set_str in sets:
        games = set_str.split(';')
        
        for game_str in games:
            if '/' in game_str:
                # Tiebreak
                if len(game_str) > 0:
                    last_char = game_str.replace('/', '')
                    if len(last_char) > 0:
                        last_char = last_char[-1]
                        if last_char in ('S', 'A'):
                            tb_winner = p1 if current_server == 1 else p2
                        elif last_char in ('R', 'D'):
                            tb_winner = p2 if current_server == 1 else p1
                        else:
                            continue
                            
                        stats[p1]['tb_played'] += 1
                        stats[p2]['tb_played'] += 1
                        stats[tb_winner]['tb_won'] += 1
                    
                # Change server for the next set (tiebreak receiver serves first)
                current_server = 3 - current_server 
                continue
                
            # Regular game
            s_pts = 0
            r_pts = 0
            
            for pt in game_str:
                server_name = p1 if current_server == 1 else p2
                returner_name = p2 if current_server == 1 else p1
                
                # Check for break point before point is played
                is_bp = (r_pts >= 3) and (r_pts >= s_pts + 1)
                
                # Check for deuce point (both have >=3 points, and are tied)
                is_deuce = (s_pts >= 3 and r_pts >= 3 and s_pts == r_pts)
                
                if pt in ('S', 'A'):
                    # Server won the point
                    if is_bp:
                        stats[server_name]['bp_faced'] += 1
                        stats[server_name]['bp_saved'] += 1
                        stats[returner_name]['bp_created'] += 1
                        
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
                        
                    if is_deuce:
                        stats[server_name]['deuce_played'] += 1
                        stats[returner_name]['deuce_played'] += 1
                        stats[returner_name]['deuce_won'] += 1
                        
                    r_pts += 1
            
            # Change server for the next game
            current_server = 3 - current_server

    return stats


def process_all_pbp(config_path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    project_root = Path(config_path).resolve().parent.parent
    pbp_dir = project_root / "data" / "raw" / "sackmann" / "tennis_pointbypoint"
    
    # We only care about ATP matches for now
    csv_files = glob.glob(str(pbp_dir / "pbp_matches_atp_*.csv")) + \
                glob.glob(str(pbp_dir / "pbp_matches_ch_*.csv")) + \
                glob.glob(str(pbp_dir / "pbp_matches_fu_*.csv"))
    
    print(f"Trovati {len(csv_files)} file point-by-point ATP/Challenger/Futures.")
    
    records = []
    
    for file in csv_files:
        print(f"Elaborazione: {Path(file).name}")
        df = pd.read_csv(file, low_memory=False)
        
        for idx, row in tqdm(df.iterrows(), total=len(df), leave=False):
            try:
                date = pd.to_datetime(row['date'], format='%d %b %y', errors='coerce')
                if pd.isna(date):
                    continue
                    
                parsed = parse_pbp_match(row)
                if not parsed:
                    continue
                    
                p1 = row['server1']
                p2 = row['server2']
                
                # Create a record for player 1
                r1 = parsed[p1]
                r1['player_name'] = p1
                r1['date'] = date
                records.append(r1)
                
                # Create a record for player 2
                r2 = parsed[p2]
                r2['player_name'] = p2
                r2['date'] = date
                records.append(r2)
            except Exception as e:
                pass # Skip problematic rows
                
    out_df = pd.DataFrame(records)
    out_df = out_df.sort_values('date').reset_index(drop=True)
    
    # Raggruppare per data e giocatore nel caso giocassero 2 match lo stesso giorno
    out_df = out_df.groupby(['date', 'player_name']).sum().reset_index()
    
    # Calculate cumulative sums for each player over time
    print("\nCalcolo delle somme cumulative storiche (Clutch Factor)...")
    
    # Sort by date
    out_df = out_df.sort_values(['player_name', 'date'])
    
    # Calculate running totals
    clutch_cols = ['bp_saved', 'bp_faced', 'bp_converted', 'bp_created', 'deuce_won', 'deuce_played', 'tb_won', 'tb_played']
    for col in clutch_cols:
        out_df[f'cum_{col}'] = out_df.groupby('player_name')[col].cumsum()
        # Shift carefully so the stats are STRICTLY PRE-MATCH
        out_df[f'cum_{col}'] = out_df.groupby('player_name')[f'cum_{col}'].shift(1).fillna(0)
    
    # Calculate percentages
    # Add a small epsilon or fillna(0) to avoid div by zero
    out_df['clutch_bp_saved_pct'] = np.where(out_df['cum_bp_faced'] > 0, out_df['cum_bp_saved'] / out_df['cum_bp_faced'], np.nan)
    out_df['clutch_bp_converted_pct'] = np.where(out_df['cum_bp_created'] > 0, out_df['cum_bp_converted'] / out_df['cum_bp_created'], np.nan)
    out_df['clutch_deuce_win_pct'] = np.where(out_df['cum_deuce_played'] > 0, out_df['cum_deuce_won'] / out_df['cum_deuce_played'], np.nan)
    out_df['clutch_tb_win_pct'] = np.where(out_df['cum_tb_played'] > 0, out_df['cum_tb_won'] / out_df['cum_tb_played'], np.nan)
    
    output_path = project_root / "data" / "processed" / "player_clutch_stats.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    
    print(f"Finito! Dati Clutch storici salvati in: {output_path}")
    print(out_df[['player_name', 'date', 'clutch_bp_saved_pct', 'clutch_bp_converted_pct']].tail(10))

if __name__ == "__main__":
    process_all_pbp("config/config.yaml")
