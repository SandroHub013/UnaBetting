import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path("g:/tennis betting")

def check_dates():
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df = pd.read_csv(unified_path)
    df['tourney_date'] = pd.to_datetime(df['tourney_date'], errors='coerce')
    
    last_db_date = df['tourney_date'].max()
    print(f"Max date in DB: {last_db_date}")
    
    # Sinner's last match
    sinner_matches = df[(df['winner_name'].str.contains('Sinner', case=False, na=False)) | 
                         (df['loser_name'].str.contains('Sinner', case=False, na=False))]
    
    if not sinner_matches.empty:
        last_sinner = sinner_matches['tourney_date'].max()
        print(f"Jannik Sinner last match in DB: {last_sinner}")
        print(f"Days since last Sinner match (relative to DB max): {(last_db_date - last_sinner).days}")
        print(f"Days since last Sinner match (relative to today): {(pd.Timestamp.now() - last_sinner).days}")
    # Alcaraz
    alc_matches = df[(df['winner_name'].str.contains('Alcaraz', case=False, na=False)) | 
                         (df['loser_name'].str.contains('Alcaraz', case=False, na=False))]
    if not alc_matches.empty:
        last_alc = alc_matches['tourney_date'].max()
        print(f"Alcaraz last match in DB: {last_alc}")

if __name__ == "__main__":
    check_dates()
