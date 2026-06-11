import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import warnings
warnings.filterwarnings('ignore')

# Mappatura statica del Court Pace Index (CPI) per i principali tornei
# Fonte: Statistiche storiche medie Hawk-Eye & ATP
# CPR (Court Pace Rating) ITF: 1 (Slow) -> 5 (Fast)
# Useremo un valore continuo 1-100 per rappresentare la velocità.
CPI_MAP = {
    # GRAND SLAMS
    'Wimbledon': 72.0,       # Grass (Molto veloce, anche se rallentata negli anni)
    'US Open': 63.0,         # Hard (Veloce)
    'Australian Open': 59.0, # Hard (Medio-Veloce)
    'Roland Garros': 28.0,   # Clay (Molto lento)
    
    # MASTERS 1000 - Hard/Indoor
    'Shanghai Masters': 73.0, # Hard (Uno dei più veloci)
    'Paris Masters': 68.0,    # Indoor Hard (Veloce)
    'Cincinnati Masters': 65.0,
    'Rogers Cup': 60.0,       # Canada
    'Miami Masters': 50.0,    # Hard (Lento per essere cemento)
    'Indian Wells Masters': 45.0, # Hard (Lentissimo, rimbalzo altissimo)
    
    # MASTERS 1000 - Clay
    'Madrid Masters': 38.0,   # Clay (Veloce per la terra, grazie all'altitudine)
    'Rome Masters': 30.0,     # Clay (Lento)
    'Monte Carlo Masters': 25.0, # Clay (Lentissimo)
    
    # ATP FINALS
    'Tour Finals': 68.0,      # Indoor Hard (Solitamente medio-veloce, es. Torino/Londra)
}

# Velocità di fallback se il torneo non è nei Masters/Slam
# Basato sulla superficie media
SURFACE_CPI_FALLBACK = {
    'Grass': 70.0,
    'Carpet': 75.0,
    'Hard': 58.0,
    'Clay': 30.0,
}

def map_cpi(tourney_name, surface):
    """
    Ritorna la stima del Court Pace Index per il torneo specificato.
    """
    name_lower = str(tourney_name).lower()
    
    for key, cpi_value in CPI_MAP.items():
        # Soft match
        if key.lower().replace(' masters', '') in name_lower or key.lower() in name_lower:
            return cpi_value
            
    # Gestione fallback
    return SURFACE_CPI_FALLBACK.get(surface, 50.0)

def add_cpi_feature(df):
    """Aggiunge la feature CPI al dataset unificato."""
    print("  -> Calcolo Court Pace Index (CPI)....")
    df['cpi'] = df.apply(lambda row: map_cpi(row['tourney_name'], row['surface']), axis=1)
    
    # Rimuovere le One-Hot originali di "surface" per forzare l'algoritmo a usare la velocità continua
    return df

def _points_for_round(tourney_level, round_name):
    """ATP official points by tournament level and round (2024 rules)."""
    # Official ATP points tables per tournament level
    ATP_POINTS = {
        'G': {'F': 2000, 'SF': 800, 'QF': 400, 'R16': 200, 'R32': 100, 'R64': 50, 'R128': 10},
        'M': {'F': 1000, 'SF': 400, 'QF': 200, 'R16': 100, 'R32': 50, 'R64': 25, 'R128': 10},
        'A': {'F': 500, 'SF': 200, 'QF': 100, 'R16': 50, 'R32': 25, 'R64': 0, 'R128': 0},
        'D': {'F': 250, 'SF': 100, 'QF': 50, 'R16': 25, 'R32': 13, 'R64': 0, 'R128': 0},
        'F': {'F': 1500, 'SF': 600, 'QF': 200, 'RR': 200, 'R16': 0, 'R32': 0, 'R64': 0, 'R128': 0},
    }

    level_table = ATP_POINTS.get(tourney_level, ATP_POINTS['D'])
    return level_table.get(round_name, 0)

def add_points_defending_feature(df):
    """
    Calcola quanti punti il giocatore sta difendendo IN QUESTO PRECISO MOMENTO 
    (ovvero quanti punti ha fatto ESATTAMENTE in questo torneo nell'anno precedente).
    """
    print("  -> Calcolo 'Punti da Difendere' (Motivazione / Pressione)....")
    
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])
    df['year'] = df['tourney_date'].dt.year
    
    # Identify how many points each player scored in each tournament per year
    # A player gets points if they WIN a match. Their final points for a tournament
    # is the points awarded for the HIGHEST round they won.
    # To simplify, we calculate points gained by the WINNER of each match.
    # The loser gets the points of the previous round.
    
    # We will build a dictionary: dict[(player_name, tourney_name, year)] = points_scored
    # First, let's calculate the points earned for winning the current match
    df['pts_earned_winner'] = df.apply(lambda row: _points_for_round(row['tourney_level'], row['round']), axis=1)
    
    # The ultimate points a player gains in a tournament is the max of the matches they won
    # If they win the Final, they get winner points. 
    # But wait, if they LOSE the Final, they get SF points (or Finalist points). 
    # Our _points_for_round logic is standard ATP. 
    # Finalist usually gets ~60% of winner points.
    
    # Create a quick summary of max points scored by player per tournament/year
    tourney_pts = df.groupby(['winner_name', 'tourney_name', 'year'])['pts_earned_winner'].max().reset_index()
    tourney_pts = tourney_pts.rename(columns={'winner_name': 'player_name', 'pts_earned_winner': 'points_scored'})
    
    # Now, for every match in the dataset, we look back 1 year exactly to find if the player played this tournament
    # and how many points they scored.
    
    def get_defending_points(player_name, tourney_name, current_year):
        match = tourney_pts[(tourney_pts['player_name'] == player_name) & 
                            (tourney_pts['tourney_name'] == tourney_name) & 
                            (tourney_pts['year'] == current_year - 1)]
        if not match.empty:
            return match['points_scored'].values[0]
        return 0.0
        
    # We map this for w_ and l_
    # This might be slow if using apply row by row, let's optimize it using a merge.
    
    # Prepare previous year data
    tourney_pts['target_year_to_defend'] = tourney_pts['year'] + 1
    
    # Merge for winner
    df = df.merge(
        tourney_pts[['player_name', 'tourney_name', 'target_year_to_defend', 'points_scored']],
        how='left',
        left_on=['winner_name', 'tourney_name', 'year'],
        right_on=['player_name', 'tourney_name', 'target_year_to_defend']
    ).rename(columns={'points_scored': 'w_defending_pts'})
    df = df.drop(columns=['player_name', 'target_year_to_defend', 'pts_earned_winner'], errors='ignore')
    
    # Merge for loser
    df = df.merge(
        tourney_pts[['player_name', 'tourney_name', 'target_year_to_defend', 'points_scored']],
        how='left',
        left_on=['loser_name', 'tourney_name', 'year'],
        right_on=['player_name', 'tourney_name', 'target_year_to_defend']
    ).rename(columns={'points_scored': 'l_defending_pts'})
    df = df.drop(columns=['player_name', 'target_year_to_defend'], errors='ignore')
    
    # Fill NAs logically
    df['w_defending_pts'] = df['w_defending_pts'].fillna(0)
    df['l_defending_pts'] = df['l_defending_pts'].fillna(0)
    
    # Drop temp cols
    df = df.drop(columns=['year'], errors='ignore')
    
    # Feature engineering logic relative to player's total ranking (Pressure Ratio)
    # Pressure ratio = points defending / current total ranking points
    df['w_pressure_ratio'] = np.where(df['winner_rank_points'] > 0, df['w_defending_pts'] / df['winner_rank_points'], 0)
    df['l_pressure_ratio'] = np.where(df['loser_rank_points'] > 0, df['l_defending_pts'] / df['loser_rank_points'], 0)
    
    return df

if __name__ == "__main__":
    # Test
    test_df = pd.DataFrame({
        'tourney_date': ['2023-05-10', '2024-05-10'],
        'tourney_name': ['Rome Masters', 'Rome Masters'],
        'tourney_level': ['M', 'M'],
        'surface': ['Clay', 'Clay'],
        'round': ['F', 'R32'],
        'winner_name': ['Djokovic N.', 'Djokovic N.'],
        'loser_name': ['Tsitsipas S.', 'Fritz T.'],
        'winner_rank_points': [10000, 10000],
        'loser_rank_points': [5000, 3000]
    })
    
    test_df = add_cpi_feature(test_df)
    test_df = add_points_defending_feature(test_df)
    print(test_df[['tourney_name', 'cpi', 'w_defending_pts', 'l_defending_pts', 'w_pressure_ratio']])
