"""
Tennis Prediction Model - Data Cleaning & Integration
Merges JeffSackmann match data with tennis-data.co.uk odds into a unified dataset.
"""

import os
import glob
import hashlib
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ============================================================
# SACKMANN DATA LOADING
# ============================================================

def load_sackmann_matches(tour="atp", min_year=2000, max_year=2026):
    """
    Load all match files from JeffSackmann repos.

    Args:
        tour: 'atp' or 'wta'
        min_year: Start year
        max_year: End year (inclusive)

    Returns:
        DataFrame with all matches
    """
    config = load_config()
    
    if tour == "atp":
        repo_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "TML-Database"
        pattern = "*.csv"
    else:
        repo_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / f"tennis_{tour}"
        pattern = f"{tour}_matches_*.csv"

    all_matches = []

    for filepath in sorted(glob.glob(str(repo_dir / pattern))):
        filename = os.path.basename(filepath)

        # Extract year from filename (e.g., atp_matches_2023.csv -> 2023, or 2024.csv -> 2024)
        try:
            val = filename.replace(".csv", "")
            if val.startswith(f"{tour}_matches_"):
                val = val.split("_")[-1]
            year = int(val)
        except ValueError:
            continue

        if year < min_year or year > max_year:
            continue

        # Skip qualifying/challenger/futures files
        if "qual" in filename.lower() or "futures" in filename.lower() or "challenger" in filename.lower():
            continue

        try:
            df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
            df["source_file"] = filename
            df["year"] = year
            all_matches.append(df)
        except Exception as e:
            print(f"  ⚠ Errore caricamento {filename}: {e}")

    if not all_matches:
        print(f"  ✗ Nessun file trovato per {tour} in {repo_dir}")
        return pd.DataFrame()

    matches = pd.concat(all_matches, ignore_index=True)
    print(f"  ✓ {tour.upper()}: {len(matches):,} partite caricate ({min_year}-{max_year})")
    return matches


def load_sackmann_rankings(tour="atp"):
    """Load all ranking files from JeffSackmann repos."""
    config = load_config()
    repo_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / f"tennis_{tour}"

    all_rankings = []
    pattern = f"{tour}_rankings_*.csv"

    for filepath in sorted(glob.glob(str(repo_dir / pattern))):
        try:
            df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
            all_rankings.append(df)
        except Exception as e:
            print(f"  ⚠ Errore: {e}")

    if not all_rankings:
        return pd.DataFrame()

    rankings = pd.concat(all_rankings, ignore_index=True)
    print(f"  ✓ {tour.upper()} Rankings: {len(rankings):,} record")
    return rankings


def load_sackmann_players(tour="atp"):
    """Load the player master file."""
    config = load_config()
    
    if tour == "atp":
        filepath = PROJECT_ROOT / config["paths"]["raw_data"] / "TML-Database" / "ATP_Database.csv"
    else:
        repo_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / f"tennis_{tour}"
        filepath = repo_dir / f"{tour}_players.csv"
        
    if not filepath.exists():
        print(f"  ✗ File giocatori non trovato: {filepath}")
        return pd.DataFrame()

    players = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
    print(f"  ✓ {tour.upper()} Players: {len(players):,} giocatori")
    return players


# ============================================================
# TENNIS-DATA.CO.UK GAP INTEGRATION
# ============================================================

def _build_name_to_id_map(matches_df):
    """
    Build a lookup from tennis-data.co.uk name format ("Tiafoe F.") to TML player ID.
    Returns dict: {td_name_lower: (tml_full_name, player_id)}
    """
    # Build full_name -> id from all TML matches
    name_to_id = {}
    for col_name, col_id in [("winner_name", "winner_id"), ("loser_name", "loser_id")]:
        if col_name not in matches_df.columns or col_id not in matches_df.columns:
            continue
        for _, row in matches_df[[col_name, col_id]].dropna().iterrows():
            name_to_id[str(row[col_name]).strip().lower()] = str(row[col_id]).strip()

    # Build lastname -> {full_name: id} index
    lastname_index = defaultdict(dict)
    for full_name, pid in name_to_id.items():
        parts = full_name.split()
        if len(parts) >= 2:
            lastname = parts[-1]
            lastname_index[lastname][full_name] = pid

    return name_to_id, lastname_index


def _resolve_td_name(td_name, name_to_id, lastname_index):
    """
    Resolve a tennis-data.co.uk player name to (tml_full_name, player_id).
    Falls back to synthetic ID if not found.
    """
    parts = td_name.strip().split()
    if not parts:
        return td_name.strip().lower(), "TD_" + hashlib.md5(td_name.encode()).hexdigest()[:8]

    # Parse: "Tiafoe F." -> lastname="tiafoe", initial="f"
    # "Carballes Baena R." -> name_parts=["carballes","baena"], initial="r"
    if parts[-1].endswith(".") and len(parts[-1]) <= 4:
        initial = parts[-1].rstrip(".").lower()
        name_parts = [p.lower() for p in parts[:-1]]
    else:
        initial = ""
        name_parts = [p.lower() for p in parts]

    # Strategy 1: Single-word lastname exact match + initial
    if len(name_parts) == 1:
        lastname = name_parts[0]
        if lastname in lastname_index:
            candidates = lastname_index[lastname]
            if len(candidates) == 1:
                fn, pid = next(iter(candidates.items()))
                return fn, pid
            # Disambiguate by initial
            if initial:
                for fn, pid in candidates.items():
                    fn_parts = fn.split()
                    if len(fn_parts) >= 2 and fn_parts[0].startswith(initial[0]):
                        return fn, pid

    # Strategy 2: Multi-word name - search TML names containing all parts
    for tml_name, pid in name_to_id.items():
        if all(part in tml_name for part in name_parts):
            if initial:
                tml_parts = tml_name.split()
                if len(tml_parts) >= 2 and tml_parts[0].startswith(initial[0]):
                    return tml_name, pid
            else:
                return tml_name, pid

    # Strategy 3: Handle apostrophes/special chars ("O Connell" -> "o'connell")
    joined = " ".join(name_parts)
    for tml_name, pid in name_to_id.items():
        normalized_tml = tml_name.replace("'", " ").replace("-", " ")
        if joined in normalized_tml:
            if not initial or tml_name.split()[0].startswith(initial[0]):
                return tml_name, pid

    # Strategy 4: Partial last name match ("Mpetshi G." -> "giovanni mpetshi perricard")
    if len(name_parts) == 1:
        for tml_name, pid in name_to_id.items():
            if name_parts[0] in tml_name.split():
                if not initial or tml_name.split()[0].startswith(initial[0]):
                    return tml_name, pid

    # Fallback: synthetic ID
    synthetic_name = td_name.strip().lower()
    synthetic_id = "TD_" + hashlib.md5(synthetic_name.encode()).hexdigest()[:8]
    return synthetic_name, synthetic_id


def _convert_odds_to_match_format(gap_df, matches_df):
    """
    Convert tennis-data.co.uk rows into TML/Sackmann column format.
    Only converts completed matches (no walkovers/retirements).
    """
    if gap_df.empty:
        return pd.DataFrame()

    # Build name resolution map
    name_to_id, lastname_index = _build_name_to_id_map(matches_df)

    # Filter to completed matches only
    gap = gap_df[gap_df["Comment"] == "Completed"].copy()
    if gap.empty:
        return pd.DataFrame()

    # Series -> tourney_level
    series_map = {"Grand Slam": "G", "Masters 1000": "M", "ATP500": "500", "ATP250": "250"}

    # Round mapping (draw-size-aware)
    round_map_gs = {
        "1st Round": "R128", "2nd Round": "R64", "3rd Round": "R32",
        "4th Round": "R16", "Quarterfinals": "QF", "Semifinals": "SF", "The Final": "F",
    }
    round_map_m = {
        "1st Round": "R64", "2nd Round": "R32", "3rd Round": "R16",
        "Quarterfinals": "QF", "Semifinals": "SF", "The Final": "F",
    }
    round_map_other = {
        "1st Round": "R32", "2nd Round": "R16",
        "Quarterfinals": "QF", "Semifinals": "SF", "The Final": "F",
    }

    rows = []
    for _, r in gap.iterrows():
        series = r.get("Series", "ATP250")

        # Resolve player names
        w_name, w_id = _resolve_td_name(str(r["Winner"]), name_to_id, lastname_index)
        l_name, l_id = _resolve_td_name(str(r["Loser"]), name_to_id, lastname_index)

        # Build score string from W1/L1 ... W5/L5
        score_parts = []
        for s in range(1, 6):
            w_games = r.get(f"W{s}")
            l_games = r.get(f"L{s}")
            if pd.notna(w_games) and pd.notna(l_games):
                score_parts.append(f"{int(w_games)}-{int(l_games)}")
        score = " ".join(score_parts) if score_parts else np.nan

        # Round mapping
        td_round = r.get("Round", "1st Round")
        if series == "Grand Slam":
            rnd = round_map_gs.get(td_round, td_round)
        elif series == "Masters 1000":
            rnd = round_map_m.get(td_round, td_round)
        else:
            rnd = round_map_other.get(td_round, td_round)

        match_date = pd.to_datetime(r["Date"], errors="coerce")

        row = {
            "tourney_name": r.get("Tournament", ""),
            "surface": r.get("Surface", "Hard"),
            "tourney_level": series_map.get(series, "250"),
            "tourney_date": match_date,
            "winner_id": w_id,
            "winner_name": w_name,
            "winner_rank": r.get("WRank"),
            "winner_rank_points": r.get("WPts"),
            "loser_id": l_id,
            "loser_name": l_name,
            "loser_rank": r.get("LRank"),
            "loser_rank_points": r.get("LPts"),
            "score": score,
            "best_of": r.get("Best of", 3),
            "round": rnd,
            "indoor": 1 if r.get("Court") == "Indoor" else 0,
            "match_num": np.nan,  # Will be NaN like 489 existing rows
            # Serve stats left as NaN - handled by median imputation downstream
            # Odds columns carried through from odds merge later
        }
        rows.append(row)

    result = pd.DataFrame(rows)
    n_synthetic = result["winner_id"].str.startswith("TD_").sum() + result["loser_id"].str.startswith("TD_").sum()
    print(f"  ✓ Convertiti {len(result):,} match da tennis-data.co.uk ({n_synthetic} player-slot con ID sintetico)")
    return result


# ============================================================
# TENNIS-DATA.CO.UK ODDS LOADING
# ============================================================

def load_odds_data(tour="atp", min_year=2000, max_year=2026):
    """
    Load historical betting odds from tennis-data.co.uk files.

    Returns:
        DataFrame with match results and bookmaker odds
    """
    config = load_config()
    odds_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "tennis_data_co_uk"

    prefix = "atp" if tour == "atp" else "wta"
    all_odds = []

    for year in range(min_year, max_year + 1):
        # Try different file extensions
        for ext in ["xlsx", "xls", "csv"]:
            filepath = odds_dir / f"{prefix}_{year}.{ext}"
            if filepath.exists():
                try:
                    if ext in ("xlsx", "xls"):
                        df = pd.read_excel(filepath)
                    else:
                        df = pd.read_csv(filepath, encoding="utf-8")
                    df["odds_year"] = year
                    all_odds.append(df)
                    break
                except Exception as e:
                    print(f"  ⚠ Errore {filepath.name}: {e}")

    if not all_odds:
        print(f"  ⚠ Nessun file quote trovato per {prefix}")
        return pd.DataFrame()

    odds = pd.concat(all_odds, ignore_index=True)
    print(f"  ✓ Quote {prefix.upper()}: {len(odds):,} record ({min_year}-{max_year})")
    return odds


# ============================================================
# DATA CLEANING
# ============================================================

def clean_sackmann_matches(df):
    """
    Clean and standardize Sackmann match data.

    - Parse dates
    - Standardize surface names
    - Calculate derived columns
    - Remove walkovers/retirements with no stats
    """
    if df.empty:
        return df

    df = df.copy()

    # Parse tournament date (handle both YYYYMMDD integers and pre-parsed datetimes)
    if not pd.api.types.is_datetime64_any_dtype(df["tourney_date"]):
        df["tourney_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
    else:
        df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")

    # Standardize surface
    surface_map = {
        "Hard": "Hard",
        "Clay": "Clay",
        "Grass": "Grass",
        "Carpet": "Carpet",
    }
    df["surface"] = df["surface"].map(surface_map).fillna(df["surface"])

    # Derive indoor/outdoor from tourney_name heuristics (if not available)
    # Sackmann doesn't have this directly, but we know some patterns

    # Calculate total points won (where stats exist)
    stats_cols = [
        "w_1stIn", "w_1stWon", "w_2ndWon", "w_svpt",
        "l_1stIn", "l_1stWon", "l_2ndWon", "l_svpt",
    ]
    has_stats = df[stats_cols].notna().all(axis=1) if all(c in df.columns for c in stats_cols) else pd.Series(False, index=df.index)
    df["has_stats"] = has_stats

    # Extract set scores
    if "score" in df.columns:
        df["n_sets"] = df["score"].apply(count_sets)

    # Create unique match key for joining with odds
    df["match_key"] = (
        df["tourney_date"].dt.strftime("%Y%m%d").fillna("") + "_" +
        df["winner_name"].fillna("").str.lower().str.strip() + "_" +
        df["loser_name"].fillna("").str.lower().str.strip()
    )

    # Tournament level mapping
    level_map = {
        "G": "Grand Slam",
        "M": "Masters 1000",
        "A": "ATP Tour",
        "D": "Davis Cup",
        "F": "Tour Finals",
    }
    if "tourney_level" in df.columns:
        df["tourney_level_name"] = df["tourney_level"].map(level_map).fillna("Other")

    print(f"  ✓ Pulizia completata: {len(df):,} partite, {has_stats.sum():,} con statistiche")
    return df


def count_sets(score):
    """Count number of sets from a score string."""
    if pd.isna(score) or not isinstance(score, str):
        return np.nan
    try:
        sets = score.strip().split(" ")
        return len(sets)
    except Exception:
        return np.nan


# ============================================================
# DATA MERGING
# ============================================================

def _extract_last_name(name):
    """
    Extract last name from different formats:
    - Sackmann: "Marcos Giron" -> "giron"
    - tennis-data: "Giron M." -> "giron"
    """
    if pd.isna(name) or not isinstance(name, str):
        return ""
    name = name.strip().lower()
    # tennis-data format: "Lastname F." or "De Minaur A."
    # Sackmann format: "FirstName LastName" or "Alex De Minaur"
    parts = name.split()
    if not parts:
        return ""
    # If last part looks like an initial (e.g. "m.", "a."), it's tennis-data format
    if parts[-1].endswith(".") and len(parts[-1]) <= 3:
        # Tennis-data format: everything before the initial is the last name
        return " ".join(parts[:-1])
    else:
        # Sackmann format: last word is the last name (simplified)
        return parts[-1]


def merge_matches_with_odds(matches_df, odds_df):
    """
    Merge Sackmann match data with tennis-data.co.uk odds.
    Uses last-name + date matching since the name formats differ:
    - Sackmann: "Marcos Giron"
    - tennis-data.co.uk: "Giron M."
    """
    if matches_df.empty or odds_df.empty:
        print("  ⚠ Impossibile unire: dati mancanti")
        return matches_df

    odds = odds_df.copy()

    # --- Prepare odds data ---
    # Identify columns (tennis-data.co.uk format)
    date_col = next((c for c in odds.columns if c.strip().lower() == "date"), None)
    winner_col = next((c for c in odds.columns if c.strip().lower() == "winner"), None)
    loser_col = next((c for c in odds.columns if c.strip().lower() == "loser"), None)

    if not all([date_col, winner_col, loser_col]):
        print(f"  ⚠ Colonne mancanti nelle quote. Trovate: {odds.columns.tolist()[:10]}...")
        return matches_df

    odds["odds_date"] = pd.to_datetime(odds[date_col], errors="coerce", dayfirst=True)
    odds["odds_w_last"] = odds[winner_col].apply(_extract_last_name)
    odds["odds_l_last"] = odds[loser_col].apply(_extract_last_name)

    # Bookmaker columns
    bookmaker_cols = [c for c in odds.columns if any(
        bk in c.upper() for bk in ["B365", "PS", "EX", "LB", "SJ", "MAX", "AVG"]
    )]
    if not bookmaker_cols:
        print("  ⚠ Colonne quote non trovate")
        return matches_df

    # Create match key for odds: date + winner_last + loser_last
    odds["merge_key"] = (
        odds["odds_date"].dt.strftime("%Y-%m-%d").fillna("") + "|" +
        odds["odds_w_last"] + "|" +
        odds["odds_l_last"]
    )

    # Keep only unique merge keys (drop duplicates, keep first)
    odds_dedup = odds.drop_duplicates(subset=["merge_key"], keep="first")
    odds_subset = odds_dedup[["merge_key"] + bookmaker_cols].copy()

    # --- Prepare match data ---
    matches = matches_df.copy()
    matches["match_w_last"] = matches["winner_name"].apply(_extract_last_name)
    matches["match_l_last"] = matches["loser_name"].apply(_extract_last_name)

    # Sackmann tourney_date is tournament start date, not match date.
    # tennis-data Date is the actual match date.
    # Strategy: try matching on a date window around the tournament.
    # First attempt: exact date match
    matches["match_date_str"] = matches["tourney_date"].dt.strftime("%Y-%m-%d").fillna("")
    matches["merge_key"] = (
        matches["match_date_str"] + "|" +
        matches["match_w_last"] + "|" +
        matches["match_l_last"]
    )

    # Merge attempt 1: exact date
    merged = matches.merge(odds_subset, on="merge_key", how="left")
    matched_exact = merged[bookmaker_cols[0]].notna().sum()

    # For unmatched rows, try matching by last names only within same year+month
    # (since tourney_date is start of tournament, actual match could be days later)
    if matched_exact < len(matches) * 0.3:
        print(f"  ℹ Exact date match basso ({matched_exact:,}), provo match per cognome+mese...")
        
        # Create a broader key: year-month + last names
        odds["broad_key"] = (
            odds["odds_date"].dt.strftime("%Y-%m").fillna("") + "|" +
            odds["odds_w_last"] + "|" +
            odds["odds_l_last"]
        )
        odds_broad = odds.drop_duplicates(subset=["broad_key"], keep="first")
        odds_broad_sub = odds_broad[["broad_key"] + bookmaker_cols].copy()

        matches["broad_key"] = (
            matches["tourney_date"].dt.strftime("%Y-%m").fillna("") + "|" +
            matches["match_w_last"] + "|" +
            matches["match_l_last"]
        )

        # Only fill unmatched rows
        unmatched_mask = merged[bookmaker_cols[0]].isna()
        if unmatched_mask.any():
            broad_merge = matches.loc[unmatched_mask].merge(
                odds_broad_sub, on="broad_key", how="left", suffixes=("", "_broad")
            )
            for col in bookmaker_cols:
                broad_col = col + "_broad" if col + "_broad" in broad_merge.columns else col
                if broad_col in broad_merge.columns:
                    merged.loc[unmatched_mask, col] = broad_merge[broad_col].values

        # Clean up
        if "broad_key" in merged.columns:
            merged = merged.drop(columns=["broad_key"], errors="ignore")
        matches = matches.drop(columns=["broad_key"], errors="ignore")

    # Final count
    total_matched = merged[bookmaker_cols[0]].notna().sum()

    # Clean up temp columns
    drop_cols = ["merge_key", "match_w_last", "match_l_last", "match_date_str"]
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns], errors="ignore")

    print(f"  ✓ Merge completato: {total_matched:,}/{len(matches_df):,} partite con quote ({total_matched/len(matches_df)*100:.1f}%)")
    return merged


# ============================================================
# MAIN PIPELINE
# ============================================================

def build_unified_dataset(tour="atp", min_year=2000, save=True):
    """
    Main pipeline: Load, clean, merge, and save unified dataset.
    Special logic: From 2024 onwards, if Sackmann is missing, we rely on tennis-data.co.uk.
    """
    print(f"\n{'=' * 60}")
    print(f"🔧 COSTRUZIONE DATASET UNIFICATO - {tour.upper()}")
    print(f"{'=' * 60}")

    # 1. Load Sackmann matches
    print("\n1. Caricamento partite Sackmann...")
    matches = load_sackmann_matches(tour=tour, min_year=min_year)

    # 2. Load odds/results from tennis-data.co.uk
    print("\n2. Caricamento quote e risultati (tennis-data.co.uk)...")
    odds = load_odds_data(tour=tour, min_year=min_year)

    # 3. Clean matches
    print("\n3. Pulizia dati Sackmann...")
    matches = clean_sackmann_matches(matches)

    # 4. Integrate recent data from tennis-data.co.uk after Sackmann cutoff
    if not odds.empty and not matches.empty:
        date_col = next((c for c in odds.columns if c.strip().lower() == "date"), None)
        if date_col:
            odds["_parsed_date"] = pd.to_datetime(odds[date_col], errors="coerce", dayfirst=True)
            sackmann_max_date = matches["tourney_date"].max()
            gap_odds = odds[odds["_parsed_date"] > sackmann_max_date]

            if len(gap_odds) > 0:
                print(f"\n  🔔 Sackmann termina il {sackmann_max_date.strftime('%Y-%m-%d')}, "
                      f"tennis-data ha {len(gap_odds)} match successivi")
                print(f"  → Integrazione dati recenti da tennis-data.co.uk...")
                gap_matches = _convert_odds_to_match_format(gap_odds, matches)
                if not gap_matches.empty:
                    # Clean the gap matches with the same pipeline
                    gap_matches = clean_sackmann_matches(gap_matches)
                    matches = pd.concat([matches, gap_matches], ignore_index=True)
                    matches = matches.sort_values("tourney_date").reset_index(drop=True)
                    print(f"  ✓ Dataset esteso a {len(matches):,} partite totali")

            odds = odds.drop(columns=["_parsed_date"], errors="ignore")

    # 5. Merge
    print("\n4. Merge dati + quote...")
    unified = merge_matches_with_odds(matches, odds)

    # 6. Deduplicate (CRITICAL to avoid leakage from repeated matches)
    initial_len = len(unified)
    unified = unified.drop_duplicates(
        subset=["tourney_date", "winner_name", "loser_name", "score"], 
        keep="first"
    )
    if len(unified) < initial_len:
        print(f"  ⚠ Rimossi {initial_len - len(unified):,} duplicati")

    # 7. Sort chronologically (strictly)
    # Using match_num ensures correct order within a tournament
    if "match_num" in unified.columns:
        unified = unified.sort_values(["tourney_date", "match_num"]).reset_index(drop=True)
    else:
        unified = unified.sort_values("tourney_date").reset_index(drop=True)

    # 8. Save
    if save:
        config = load_config()
        output_path = PROJECT_ROOT / config["paths"]["processed_data"] / f"{tour}_unified.csv"
        unified.to_csv(output_path, index=False)
        print(f"\n  💾 Salvato: {output_path}")
        print(f"  📊 {len(unified):,} partite totali")

        # Print surface distribution
        if "surface" in unified.columns:
            print(f"\n  Distribuzione superfici:")
            for surface, count in unified["surface"].value_counts().items():
                pct = count / len(unified) * 100
                print(f"    {surface}: {count:,} ({pct:.1f}%)")

    return unified


if __name__ == "__main__":
    # Build ATP dataset
    atp_data = build_unified_dataset(tour="atp", min_year=2000)

    # Build WTA dataset
    wta_data = build_unified_dataset(tour="wta", min_year=2007)

    print("\n✅ Pipeline di pulizia completata!")
