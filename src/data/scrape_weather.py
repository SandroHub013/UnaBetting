import pandas as pd
import numpy as np
import time
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import openmeteo_requests
import requests_cache
from retry_requests import retry
import warnings

warnings.filterwarnings('ignore')
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = -1)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

def clean_tourney_name(name):
    """Pulisce il nome del torneo per migliorare il geocoding"""
    name = str(name)
    # Rimuovi anni, numeri, ecc
    import re
    name = re.sub(r'\b20\d{2}\b', '', name)
    name = re.sub(r'\b19\d{2}\b', '', name)
    
    # Rimuovi diciture comuni
    stopwords = ['ATP', 'Open', 'Masters', '1000', '500', '250', 'Championships', 'Tour', 'Finals', 'Grand Prix', 'International', 'Cup']
    for word in stopwords:
        name = name.replace(word, '')
    
    return name.strip()

def geocode_tournaments(df, top_n=200):
    """Geolocalizza i top N tornei più frequenti per limitare le chiamate API."""
    print(f"  -> Estrazione dei {top_n} tornei principali...")
    
    tourney_counts = df['tourney_name'].value_counts()
    top_tourneys = tourney_counts.head(top_n).index.tolist()
    
    geolocator = Nominatim(user_agent="tennis_predictor_bot")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2) # Nominatim policy: max 1 req/sec
    
    location_dict = {}
    print("  -> Inizio Geocoding (potrebbe richiedere un paio di minuti)...")
    
    for t in top_tourneys:
        cleaned_name = clean_tourney_name(t)
        # Alcuni override manuali per le sedi più famose
        if 'wimbledon' in t.lower(): cleaned_name = 'London, UK'
        if 'us open' in t.lower(): cleaned_name = 'New York, USA'
        if 'roland garros' in t.lower() or 'french open' in t.lower(): cleaned_name = 'Paris, France'
        if 'australian open' in t.lower(): cleaned_name = 'Melbourne, Australia'
        if 'indian wells' in t.lower(): cleaned_name = 'Indian Wells, CA, USA'
        
        try:
            location = geocode(cleaned_name)
            if location:
                location_dict[t] = (location.latitude, location.longitude)
            else:
                # Se fallisce, usiamo una città fittizia (media globale) o skippiamo
                location_dict[t] = (None, None)
        except Exception as e:
            location_dict[t] = (None, None)
            
    return location_dict

def get_historical_weather(lat, lon, start_date, end_date):
    """Scarica il meteo storico da Open-Meteo per una coordinata e un range di date."""
    if pd.isna(lat) or pd.isna(lon):
        return None
        
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
        "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
        "timezone": "auto"
    }
    
    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        
        daily = response.Daily()
        daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
        daily_precipitation_sum = daily.Variables(1).ValuesAsNumpy()
        daily_wind_speed_10m_max = daily.Variables(2).ValuesAsNumpy()
        
        dates = pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        )
        
        weather_data = pd.DataFrame({
            "date": dates.tz_localize(None).normalize(), # Rimuovi timezone per il merge
            "temp_max": daily_temperature_2m_max,
            "precipitation": daily_precipitation_sum,
            "wind_speed": daily_wind_speed_10m_max
        })
        return weather_data
        
    except Exception as e:
        print(f"Errore API meteo: {e}")
        return None

def add_weather_features(df):
    """Pipeline principale per aggiungere il meteo storico al dataset."""
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])
    
    # Prendi solo i match dopo il 2000 per evitare di sovraccaricare l'API con dati vecchissimi
    recent_df = df[df['tourney_date'].dt.year >= 2000].copy()
    
    # 1. Geocodifica i top 100 tornei (coprono >80% dei match)
    loc_dict = geocode_tournaments(recent_df, top_n=100)
    
    # 2. Estrai il set di date uniche per ogni torneo per fare query batch
    print("  -> Download storico meteo via API Open-Meteo...")
    
    weather_records = []
    
    for tourney_name, (lat, lon) in loc_dict.items():
        if lat is None: continue
            
        t_matches = recent_df[recent_df['tourney_name'] == tourney_name]
        
        # Minimizza le chiamate API trovando min e max date per ogni anno in cui si è giocato
        for year, group in t_matches.groupby(t_matches['tourney_date'].dt.year):
            start_d = group['tourney_date'].min()
            end_d = group['tourney_date'].max() + pd.Timedelta(days=14) # Un torneo dura ~14gg max
            
            # Limita end_date alla data odierna meno 5 giorni (Open Meteo archive delay)
            max_allowed = pd.Timestamp.today().normalize() - pd.Timedelta(days=5)
            if end_d > max_allowed: end_d = max_allowed
            if start_d > end_d: continue
            
            w_df = get_historical_weather(lat, lon, start_d, end_d)
            if w_df is not None:
                w_df['tourney_name'] = tourney_name
                weather_records.append(w_df)
                
    if not weather_records:
        return df
        
    all_weather = pd.concat(weather_records, ignore_index=True)
    
    # 3. Merge weather back to original dataframe
    # Arrotondiamo la data del match alla mezzanotte per il merge
    df['match_day'] = df['tourney_date'].dt.normalize()
    
    # Siccome in alcuni database la tourney_date è l'inizio del torneo e non il giorno esatto del match,
    # facciamo in modo da prendere il meteo dei primi 3-4 giorni o usiamo la media della settimana
    # Per semplicità incrociamo la data esatta o fill_forward.
    
    print("  -> Merge meteo nel dataset unificato...")
    df = df.merge(
        all_weather,
        how='left',
        left_on=['tourney_name', 'match_day'],
        right_on=['tourney_name', 'date']
    )
    
    # Pulizia colonne
    df = df.drop(columns=['date', 'match_day'], errors='ignore')
    
    # Imputazione NaNs usando la media globale per non rompere il modello
    df['temp_max'] = df['temp_max'].fillna(22.0)
    df['precipitation'] = df['precipitation'].fillna(0.0)
    df['wind_speed'] = df['wind_speed'].fillna(10.0)
    
    print("  ✓ Feature ambientali (Meteo) storiche aggiunte!")
    return df

def produce_weather_dataset():
    """Genera il dataset meteo per tutti i match e lo salva come CSV pre-calcolato."""
    print("Iniziando il processo di Scraping Meteo & Geocoding...")
    import os
    
    input_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    if not input_path.exists():
        print("Dataset caricato: Fake fallback")
        df = pd.DataFrame({
            'tourney_name': ['Wimbledon', 'US Open', 'Wimbledon', 'Rome Masters'],
            'tourney_date': ['2023-07-03', '2023-08-28', '2022-06-27', '2023-05-10'],
            'surface': ['Grass', 'Hard', 'Grass', 'Clay']
        })
    else:
        df = pd.read_csv(input_path, low_memory=False)
        print(f"Dataset caricato. Partite totali: {len(df)}")
        
    weather_df = add_weather_features(df)
    
    # Save the weather mapping locally
    output_path = PROJECT_ROOT / "data" / "processed" / "tourney_weather.csv"
    weather_cols = ['tourney_name', 'tourney_date', 'temp_max', 'precipitation', 'wind_speed']
    
    # Rimuoviamo duplicati (stesso torneo e data) prima di salvare
    final_weather = weather_df[weather_cols].drop_duplicates()
    final_weather.to_csv(output_path, index=False)
    print(f"\nSalvataggio completato: {output_path}")

if __name__ == "__main__":
    produce_weather_dataset()
