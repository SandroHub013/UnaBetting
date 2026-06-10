"""
Tennis Prediction Model - Feature Building Pipeline
Orchestrates ELO + player stats into a final feature matrix ready for ML.
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path

from src.features.elo import EloRating
from src.features.player_stats import build_match_features
from src.features.sota_features import add_cpi_feature, add_points_defending_feature
from src.data.label_markets import parse_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def build_all_features(tour="atp"):
    """
    Master feature engineering pipeline:
    1. Load unified dataset
    2. Compute ELO ratings
    3. Compute rolling player stats + H2H + fatigue
    4. Create final feature matrix ready for model training

    Returns:
        DataFrame with all features
    """
    config = load_config()
    print(f"\n{'=' * 60}")
    print(f"⚡ FEATURE ENGINEERING PIPELINE - {tour.upper()}")
    print(f"{'=' * 60}")

    # 1. Load unified dataset
    input_path = PROJECT_ROOT / config["paths"]["processed_data"] / f"{tour}_unified.csv"
    if not input_path.exists():
        print(f"  ✗ Dataset non trovato: {input_path}")
        print(f"  → Esegui prima: python -m src.data.clean")
        return pd.DataFrame()

    print("\n1. Caricamento dataset unificato...")
    df = pd.read_csv(input_path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
    
    # CRITICAL: Strict sorting to avoid temporal leakage
    # Within a tourney_date, we must follow match_num to avoid processing Final before Round 1
    df = df.sort_values(["tourney_date", "match_num"]).reset_index(drop=True)
    print(f"  ✓ {len(df):,} partite caricate")

    # 2. Compute ELO ratings
    print("\n2. Calcolo ELO ratings...")
    elo_config = config["features"]["elo"]
    elo = EloRating(
        k_factor=elo_config["k_factor"],
        k_factor_grand_slam=elo_config["k_factor_grand_slam"],
        initial_rating=elo_config["initial_rating"],
        surface_weight=elo_config["surface_weight"],
    )
    df = elo.process_matches(df)

    # 2.5 Parse scores BEFORE player stats (needed for totals rolling features)
    print("\n2.5 Parsing score per total_games/game_diff...")
    labels = df['score'].apply(parse_score)
    df[['winner_games', 'loser_games', 'total_games', 'game_diff']] = pd.DataFrame(labels.tolist(), index=df.index)

    # 3. Compute player stats (now has access to total_games, game_diff for totals features)
    print("\n3. Calcolo statistiche giocatori...")
    df = build_match_features(df)

    # 4. Add Contextual & Clutch & SOTA features
    print("\n4. Features contestuali, Clutch e SOTA...")
    df = _add_contextual_features(df)
    df = _add_clutch_features(df)
    df = add_cpi_feature(df)
    df = add_points_defending_feature(df)
    df = _add_weather_features(df)
    df = _add_implied_probabilities(df)
    
    # 5. Create modeling-ready format
    print("\n5. Preparazione feature matrix...")
    feature_df = _prepare_feature_matrix(df)

    # 6. Save
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    feature_df.to_csv(features_path, index=False)
    print(f"\n  💾 Feature salvate: {features_path}")
    print(f"  📊 Shape: {feature_df.shape}")

    # Also save the full enriched dataset
    enriched_path = PROJECT_ROOT / config["paths"]["processed_data"] / f"{tour}_enriched.csv"
    df.to_csv(enriched_path, index=False)

    return feature_df

def _add_implied_probabilities(df):
    """
    Calculate the bookmaker's implied probability (margin removed).
    This acts as a powerful SOTA baseline feature, transforming the model into a differential error-corrector.
    """
    df = df.copy()

    # We use B365 as primary, PS as secondary, Avg as fallback
    # Convert to numeric to handle mixed types from gap matches
    w_odds = pd.to_numeric(df.get("B365W", pd.Series(np.nan, index=df.index)), errors="coerce").fillna(
        pd.to_numeric(df.get("PSW", pd.Series(np.nan, index=df.index)), errors="coerce")).fillna(
        pd.to_numeric(df.get("AvgW", pd.Series(np.nan, index=df.index)), errors="coerce"))

    l_odds = pd.to_numeric(df.get("B365L", pd.Series(np.nan, index=df.index)), errors="coerce").fillna(
        pd.to_numeric(df.get("PSL", pd.Series(np.nan, index=df.index)), errors="coerce")).fillna(
        pd.to_numeric(df.get("AvgL", pd.Series(np.nan, index=df.index)), errors="coerce"))
    
    df["w_implied_prob"] = (1.0 / w_odds).replace(np.inf, np.nan)
    df["l_implied_prob"] = (1.0 / l_odds).replace(np.inf, np.nan)
    
    # Normalize to remove overround (bookmaker margin)
    margin = df["w_implied_prob"] + df["l_implied_prob"]
    df["w_implied_prob"] = df["w_implied_prob"] / margin
    df["l_implied_prob"] = df["l_implied_prob"] / margin
    
    df["diff_implied_prob"] = df["w_implied_prob"] - df["l_implied_prob"]

    # Perspective-symmetric flag: lets the model distinguish real market info
    # from the 0.5/0.5 sentinel fill below (and lets downstream consumers
    # filter no-odds rows without re-deriving from raw odds columns).
    df["has_odds"] = df["w_implied_prob"].notna().astype(float)

    # Fill missing implied probabilities with 0.5 (coin flip) to not drop historical data
    df["w_implied_prob"] = df["w_implied_prob"].fillna(0.5)
    df["l_implied_prob"] = df["l_implied_prob"].fillna(0.5)
    df["diff_implied_prob"] = df["diff_implied_prob"].fillna(0.0)
    
    print("  ✓ Probabilità implicite del mercato (SOTA Phase 4) calcolate")
    return df


def _add_contextual_features(df):
    """Add contextual features: surface dummies, tournament level, etc."""
    df = df.copy()

    # Explicit Surface one-hot encoding to avoid leaked continuous variables
    if "surface" in df.columns:
        df["surface_Hard"] = (df["surface"] == "Hard").astype(int)
        df["surface_Clay"] = (df["surface"] == "Clay").astype(int)
        df["surface_Grass"] = (df["surface"] == "Grass").astype(int)

    # Tournament level dummies
    if "tourney_level" in df.columns:
        level_dummies = pd.get_dummies(df["tourney_level"], prefix="level")
        df = pd.concat([df, level_dummies], axis=1)

    # Ranking difference
    if "winner_rank" in df.columns and "loser_rank" in df.columns:
        df["rank_diff"] = df["loser_rank"] - df["winner_rank"]  # Positive = winner ranked higher
        df["rank_ratio"] = df["loser_rank"] / df["winner_rank"].replace(0, np.nan)

    # Age difference
    if "winner_age" in df.columns and "loser_age" in df.columns:
        df["age_diff"] = df["winner_age"] - df["loser_age"]

    # Height difference
    if "winner_ht" in df.columns and "loser_ht" in df.columns:
        df["height_diff"] = df["winner_ht"] - df["loser_ht"]

    # Handedness
    if "winner_hand" in df.columns:
        df["w_is_lefty"] = (df["winner_hand"] == "L").astype(int)
    if "loser_hand" in df.columns:
        df["l_is_lefty"] = (df["loser_hand"] == "L").astype(int)

    # Seed indicator
    if "winner_seed" in df.columns:
        df["w_is_seeded"] = df["winner_seed"].notna().astype(int)
    if "loser_seed" in df.columns:
        df["l_is_seeded"] = df["loser_seed"].notna().astype(int)

    # === TOTALS-ORIENTED FEATURES ===
    # best_of (3 or 5 sets - critical for totals ceiling)
    if "best_of" in df.columns:
        df["best_of_5"] = (df["best_of"] == 5).astype(int)

    # Round encoded as ordinal (later rounds = tighter matches = more games)
    round_map = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7, "RR": 4}
    if "round" in df.columns:
        df["round_ordinal"] = df["round"].map(round_map).fillna(3)

    # Competitiveness: absolute ELO/prob difference (close matches → more games)
    if "elo_win_prob" in df.columns:
        df["abs_elo_prob_diff"] = (df["elo_win_prob"] - 0.5).abs()
    if "diff_implied_prob" in df.columns:
        df["abs_implied_prob_diff"] = df["diff_implied_prob"].abs()

    # Additive features (SUM of both players' stats → totals signal)
    for w in [10, 20, 50]:
        # Sum of ace rates → more holds → more tiebreaks
        w_ace = f"w_ace_rate_{w}"
        l_ace = f"l_ace_rate_{w}"
        if w_ace in df.columns and l_ace in df.columns:
            df[f"sum_ace_rate_{w}"] = df[w_ace].fillna(0) + df[l_ace].fillna(0)

        # Sum of break point save pct → both saving well → longer sets
        w_bp = f"w_bp_save_pct_{w}"
        l_bp = f"l_bp_save_pct_{w}"
        if w_bp in df.columns and l_bp in df.columns:
            df[f"sum_bp_save_pct_{w}"] = df[w_bp].fillna(0) + df[l_bp].fillna(0)

        # Sum/Min of avg total games → how many games each player's matches produce
        w_tg = f"w_avg_total_games_{w}"
        l_tg = f"l_avg_total_games_{w}"
        if w_tg in df.columns and l_tg in df.columns:
            df[f"sum_avg_total_games_{w}"] = df[w_tg].fillna(0) + df[l_tg].fillna(0)
            df[f"min_avg_total_games_{w}"] = df[[w_tg, l_tg]].min(axis=1)

        # Sum of hold pct → service dominance from both sides
        w_hold = f"w_hold_pct_{w}"
        l_hold = f"l_hold_pct_{w}"
        if w_hold in df.columns and l_hold in df.columns:
            df[f"sum_hold_pct_{w}"] = df[w_hold].fillna(0) + df[l_hold].fillna(0)
        # Sum of tiebreak rates
        w_tb = f"w_tiebreak_rate_{w}"
        l_tb = f"l_tiebreak_rate_{w}"
        if w_tb in df.columns and l_tb in df.columns:
            df[f"sum_tiebreak_rate_{w}"] = df[w_tb].fillna(0) + df[l_tb].fillna(0)

        # Sum of deciding set pct
        w_ds = f"w_deciding_set_pct_{w}"
        l_ds = f"l_deciding_set_pct_{w}"
        if w_ds in df.columns and l_ds in df.columns:
            df[f"sum_deciding_set_pct_{w}"] = df[w_ds].fillna(0) + df[l_ds].fillna(0)

    # === SAFE INTERACTION FEATURES (Asymmetric Base) ===
    # We create them as w_ and l_ individually. The loop below will safely generate the diff_ without leakage.
    
    # 1. Elo x Form
    if "w_elo" in df.columns and "w_form_ewm" in df.columns:
        df["w_elo_x_form"] = df["w_elo"] * df["w_form_ewm"]
        df["l_elo_x_form"] = df["l_elo"] * df["l_form_ewm"]
        
    # 2. Age x Fatigue
    if "winner_age" in df.columns and "w_decay_minutes_14d" in df.columns:
        df["w_age_x_fatigue"] = df["winner_age"] * df["w_decay_minutes_14d"]
        df["l_age_x_fatigue"] = df["loser_age"] * df["l_decay_minutes_14d"]

    # AUTO-GENERATE DIFFS
    # Compute differential features for all w_/l_ symmetric pairs that don't already have one
    for c in df.columns.tolist():
        if c.startswith("w_"):
            base = c[2:]
            l_col = f"l_{base}"
            diff_col = f"diff_{base}"
            if l_col in df.columns and diff_col not in df.columns:
                if pd.api.types.is_numeric_dtype(df[c]) and pd.api.types.is_numeric_dtype(df[l_col]):
                    df[diff_col] = df[c] - df[l_col]

    print(f"  ✓ Feature contestuali aggiunte (+ totals combinatorie + diffs automatiche)")
    return df



def _add_clutch_features(df):
    """Add historically computed Clutch Factor metrics using pandas merge_asof"""
    clutch_path = PROJECT_ROOT / "data" / "processed" / "player_clutch_stats.csv"
    if not clutch_path.exists():
        print("  ⚠ Dataset Clutch non trovato. Saltando feature clutch...")
        return df
        
    clutch_df = pd.read_csv(clutch_path)
    clutch_df['date'] = pd.to_datetime(clutch_df['date'])
    
    # Must sort by date for merge_asof
    df = df.sort_values('tourney_date')
    clutch_df = clutch_df.sort_values('date')
    
    # Resolve NaNs that crash merge_asof
    df_clean = df.copy()
    df_clean['winner_name'] = df_clean['winner_name'].fillna('Unknown')
    df_clean['loser_name'] = df_clean['loser_name'].fillna('Unknown')
    df_clean['tourney_date'] = df_clean['tourney_date'].fillna(pd.Timestamp('1970-01-01'))
    df_clean = df_clean.sort_values('tourney_date')

    # Merge for winner (strictly backward, using allow_exact_matches=False ensures pre-match stats)
    winner_clutch = pd.merge_asof(
        df_clean[['tourney_date', 'winner_name']].rename(columns={'winner_name':'player_name'}),
        clutch_df,
        left_on='tourney_date',
        right_on='date',
        by='player_name',
        direction='backward',
        allow_exact_matches=False
    )
    
    # Merge for loser
    loser_clutch = pd.merge_asof(
        df_clean[['tourney_date', 'loser_name']].rename(columns={'loser_name':'player_name'}),
        clutch_df,
        left_on='tourney_date',
        right_on='date',
        by='player_name',
        direction='backward',
        allow_exact_matches=False
    )
    
    # Add columns to main df
    clutch_cols = ['clutch_bp_saved_pct', 'clutch_bp_converted_pct', 'clutch_deuce_win_pct', 'clutch_tb_win_pct']
    for col in clutch_cols:
        df[f'w_{col}'] = winner_clutch[col].values
        df[f'l_{col}'] = loser_clutch[col].values
        
    print(f"  ✓ Feature Clutch integrate (Mancanti w/l: {df['w_clutch_bp_saved_pct'].isna().sum()} / {df['l_clutch_bp_saved_pct'].isna().sum()})")
    
    # In case a player has no PBP history, we fill with the average (approx 0.5 for most)
    df = df.fillna({
        'w_clutch_bp_saved_pct': 0.6,
        'l_clutch_bp_saved_pct': 0.6,
        'w_clutch_bp_converted_pct': 0.4,
        'l_clutch_bp_converted_pct': 0.4,
        'w_clutch_deuce_win_pct': 0.5,
        'l_clutch_deuce_win_pct': 0.5,
        'w_clutch_tb_win_pct': 0.5,
        'l_clutch_tb_win_pct': 0.5,
    })
    
    # We must sort back to original order to avoid messing up the rest of the pipeline
    df = df.sort_values(["tourney_date", "match_num"]).reset_index(drop=True)
    return df

def _add_weather_features(df):
    """Add historically scraped weather parameters."""
    weather_path = PROJECT_ROOT / "data" / "processed" / "tourney_weather.csv"
    if not weather_path.exists():
        print("  ⚠ Dataset Meteo non trovato. Saltando feature ambientali...")
        return df
        
    weather_df = pd.read_csv(weather_path)
    weather_df['tourney_date'] = pd.to_datetime(weather_df['tourney_date'])
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])
    
    # Merge exact tournament and date
    df = df.merge(
        weather_df,
        how='left',
        on=['tourney_name', 'tourney_date']
    )
    
    # Impute missing with averages
    df['temp_max'] = df['temp_max'].fillna(22.0)
    df['precipitation'] = df['precipitation'].fillna(0.0)
    df['wind_speed'] = df['wind_speed'].fillna(10.0)
    
    print(f"  ✓ Feature Ambientali SOTA integrate")
    return df

def _prepare_feature_matrix(df):
    """
    Create modeling-ready feature matrix.
    Pivots the data so each row represents a match with p1/p2 perspective
    (randomly assigned to avoid always having the winner as p1).
    """
    # List of feature columns we want for modeling (MUST NOT INCLUDE POST-MATCH STATS)
    # Be very specific to avoid data leakage (e.g. w_bpSaved vs w_bp_saved_avg_10)
    feature_cols = []
    
    # 1. ELO Features
    elo_prefixes = ["w_elo", "l_elo", "w_surface_elo", "l_surface_elo", "elo_win_prob", "elo_surface_win_prob", "w_vs_", "l_vs_"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in elo_prefixes)])
    
    # 2. Player Rolling Stats (identified by window suffixes _10, _20, _50)
    stats_prefixes = ["w_win_rate", "l_win_rate", "w_win_rate_surface", "l_win_rate_surface",
                      "w_n_matches", "l_n_matches", "w_n_matches_surface", "l_n_matches_surface"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in stats_prefixes)])
    
    # 2.5 Clutch Features
    clutch_prefixes = ["w_clutch", "l_clutch"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in clutch_prefixes)])
    
    # 3. SOTA Features (CPI, Points Defending, Weather)
    sota_prefixes = ["cpi", "w_defending_pts", "l_defending_pts", "w_pressure_ratio", "l_pressure_ratio", "temp_max", "precipitation", "wind_speed"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in sota_prefixes)])
    
    # Add other rolling features (ace_rate, hold_pct, etc.) NOT already captured above
    window_suffixes = ["_10", "_20", "_50"]
    already_captured = set(feature_cols)
    rolling_stats = [c for c in df.columns if any(c.endswith(s) for s in window_suffixes)
                     and (c.startswith("w_") or c.startswith("l_"))
                     and c not in already_captured]
    feature_cols.extend(rolling_stats)
    
    # 3. H2H and Fatigue (incl. cumulative load: games/minutes in last 14d)
    fatigue_prefixes = ["w_h2h", "l_h2h", "w_days_since", "l_days_since",
                        "w_matches_last", "l_matches_last", "w_sets_last", "l_sets_last",
                        "w_games_last", "l_games_last", "w_minutes_last", "l_minutes_last",
                        "w_decay_minutes", "l_decay_minutes"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in fatigue_prefixes)])

    # 3.1 Momentum / recent form (high signal for close matches)
    momentum_prefixes = ["w_form_ewm", "l_form_ewm", "w_current_streak", "l_current_streak",
                         "w_recent_form_5", "l_recent_form_5"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in momentum_prefixes)])
    
    # 3.5 Market Probabilities
    market_prefixes = ["w_implied_prob", "l_implied_prob", "diff_implied_prob", "has_odds"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in market_prefixes)])
    
    # 4. Contextual Features
    context_prefixes = ["diff_", "rank_diff", "rank_ratio",
                        "age_diff", "height_diff", "w_is_", "l_is_", "w_ht", "l_ht",
                        "surface_Hard", "surface_Clay", "surface_Grass",
                        "level_G", "level_M", "level_A", "level_C", "level_S", "level_F", "level_D"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in context_prefixes)])

    # 5. Totals-oriented features (additive, closeness, match format)
    totals_prefixes = ["best_of_5", "round_ordinal", "abs_elo_prob_diff", "abs_implied_prob_diff",
                       "sum_ace_rate", "sum_bp_save_pct", "sum_avg_total_games", "min_avg_total_games",
                       "sum_hold_pct", "sum_tiebreak_rate", "sum_deciding_set_pct"]
    feature_cols.extend([c for c in df.columns if any(c.startswith(p) for p in totals_prefixes)])
    
    # Deduplicate (PRESERVE ORDER — set() is non-deterministic across runs/Python versions
    # and can desync training vs inference column order). Then REMOVE ANY LEAKS explicitly.
    feature_cols = list(dict.fromkeys(feature_cols))
    
    # Post-match stats that we MUST remove (they only exist for the current match)
    leaky_stats = ["ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced", "ret_rtn", "n_sets", "duration"]
    
    # Nuclear option: remove any column that looks like a post-match stat from the WHOLE dataframe
    all_possible_leaks = []
    for p in ["w_", "l_", "diff_"]:
        for s in leaky_stats:
            all_possible_leaks.append(f"{p}{s}")
    
    leaks_removed = [c for c in df.columns if c in all_possible_leaks]
    df = df.drop(columns=leaks_removed, errors="ignore")
    
    if leaks_removed:
        print(f"  ⚠ NUCLEAR FILTER: Rimossi {len(leaks_removed)} leak: {sorted(leaks_removed)}")
        
    # Update feature_cols to reflect removals
    feature_cols = [c for c in feature_cols if c not in leaks_removed]
    print(f"  ✓ Features selezionate: {len(feature_cols)}")

    # Metadata columns
    meta_cols = ["tourney_date", "tourney_name", "surface", "tourney_level",
                 "winner_name", "loser_name", "winner_id", "loser_id", "score"]
                 
    # Propagate original raw odds as metadata for backtesting (NOT for training)
    odds_cols = [c for c in df.columns if any(bk in c.upper() for bk in ["B365", "PS", "MAX", "AVG"])]
    meta_cols.extend(odds_cols)
    
    meta_cols = [c for c in meta_cols if c in df.columns]

    # Targets:
    # 1. H2H (winner always wins = 1) — rows are stored winner-POV; train.py
    #    symmetrizes by flipping 50% of rows (w_/l_, diff_) AND flipping target → 0.
    #    See src/models/train.py _symmetrize_features (~line 170-213). Do NOT change
    #    this constant without updating the symmetrization step.
    # 2. Totals (total games)
    # 3. Spread (game diff)
    df["target"] = 1
    
    all_cols = meta_cols + feature_cols + ["target", "total_games", "game_diff"]
    all_cols = [c for c in all_cols if c in df.columns]
    
    result = df[all_cols].copy()

    # Remove rows with too many missing features
    n_features = len(feature_cols)
    feature_present = result[feature_cols].notna().sum(axis=1) if feature_cols else pd.Series(0, index=result.index)
    result = result[feature_present >= n_features * 0.3].reset_index(drop=True)

    print(f"  ✓ Feature matrix salvata: {result.shape[0]:,} righe × {result.shape[1]} colonne")
    return result


if __name__ == "__main__":
    atp_features = build_all_features(tour="atp")
    print("\n✅ Feature engineering completato!")
