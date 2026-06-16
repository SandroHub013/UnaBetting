import os
from dotenv import load_dotenv
load_dotenv()

import json
import pandas as pd
import numpy as np
import joblib
import yaml
from pathlib import Path
from datetime import datetime, timezone
import dateutil.parser
from difflib import SequenceMatcher
from src.features.sota_features import map_cpi

from src.runtime_paths import DATA_ROOT as PROJECT_ROOT  # writable+seeded root (repo root in dev)

def load_resources(tour="atp"):
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    cache_path = PROJECT_ROOT / "models" / f"{tour}_live_engines.pkl"
    
    # Legacy-pickle shim: ensembles saved before 2026-06-10 were pickled while
    # train.py ran as __main__, so they reference "__main__.PreFittedEnsemble".
    # Make that name resolvable from ANY entrypoint (TUI, dashboard, -c, -m).
    import sys
    from src.models.train import PreFittedEnsemble
    _main = sys.modules.get("__main__")
    if _main is not None and not hasattr(_main, "PreFittedEnsemble"):
        _main.PreFittedEnsemble = PreFittedEnsemble

    def _load_model_artifact(path):
        """Load model from artifact. Supports both new bundle format
        ({'model': ..., 'feature_cols': [...]}) and legacy bare-model pickles.
        Returns (model, feature_cols_or_None).
        """
        obj = joblib.load(path)
        if isinstance(obj, dict) and "model" in obj:
            return obj["model"], obj.get("feature_cols")
        return obj, None

    # Load Multi-Models (XGBoost for H2H: best accuracy 78.8%, ROC AUC 0.885)
    model_h2h, fc_h2h = _load_model_artifact(PROJECT_ROOT / "models" / f"{tour}_target_xgboost.pkl")
    model_spread, _ = _load_model_artifact(PROJECT_ROOT / "models" / f"{tour}_game_diff_xgboost.pkl")
    model_totals, _ = _load_model_artifact(PROJECT_ROOT / "models" / f"{tour}_total_games_ensemble.pkl")

    scaler = joblib.load(PROJECT_ROOT / "models" / f"{tour}_scaler.pkl")
    features_meta_path = PROJECT_ROOT / "models" / f"{tour}_features.txt"
    medians_path = PROJECT_ROOT / "models" / f"{tour}_medians.pkl"

    # Load all
    state = joblib.load(cache_path)

    # Prefer feature_cols bundled with the h2h artifact (authoritative).
    # Fall back to legacy txt file for models trained before bundle format.
    if fc_h2h:
        feature_cols = list(fc_h2h)
    else:
        with open(features_meta_path, "r") as f:
            feature_cols = [line.strip() for line in f if line.strip()]

    medians = joblib.load(medians_path) if medians_path.exists() else {}

    return config, state['elo'], state['stats'], {
        'h2h': model_h2h,
        'spread': model_spread,
        'totals': model_totals
    }, scaler, feature_cols, medians

# Tournament classification maps for dynamic detection
# Searched in both match string AND sport_key/sport_title from OddsAPI
TOURNEY_SURFACE_MAP = {
    'australian open': 'Hard', 'us open': 'Hard', 'wimbledon': 'Grass',
    'roland garros': 'Clay', 'french open': 'Clay',
    'indian wells': 'Hard', 'miami': 'Hard', 'monte carlo': 'Clay',
    'madrid': 'Clay', 'rome': 'Clay', 'roma': 'Clay',
    'shanghai': 'Hard', 'paris': 'Hard', 'cincinnati': 'Hard',
    'canada': 'Hard', 'montreal': 'Hard', 'toronto': 'Hard',
    'dubai': 'Hard', 'doha': 'Hard', 'rotterdam': 'Hard',
    'barcelona': 'Clay', 'acapulco': 'Hard', 'halle': 'Grass',
    "queen's": 'Grass', 'queens': 'Grass',
    'adelaide': 'Hard', 'brisbane': 'Hard', 'auckland': 'Hard',
    'marseille': 'Hard', 'delray beach': 'Hard', 'lyon': 'Clay',
    'eastbourne': 'Grass', 'hertogenbosch': 'Grass', 'mallorca': 'Grass',
    'monte_carlo': 'Clay', 'montecarlo': 'Clay',
    'buenos aires': 'Clay', 'rio': 'Clay', 'sao paulo': 'Clay',
    'houston': 'Clay', 'marrakech': 'Clay', 'bucharest': 'Clay',
    'umag': 'Clay', 'bastad': 'Clay', 'gstaad': 'Clay',
    'hamburg': 'Clay', 'kitzbuhel': 'Clay', 'cordoba': 'Clay',
    'estoril': 'Clay', 'geneva': 'Clay', 'parma': 'Clay',
    'cagliari': 'Clay', 'belgrade': 'Clay', 'sardegna': 'Clay',
    'newport': 'Grass', 's hertogenbosch': 'Grass',
}

TOURNEY_LEVEL_MAP = {
    'australian open': 'G', 'us open': 'G', 'wimbledon': 'G',
    'roland garros': 'G', 'french open': 'G',
    'indian wells': 'M', 'miami': 'M', 'monte carlo': 'M',
    'monte_carlo': 'M', 'montecarlo': 'M',
    'madrid': 'M', 'rome': 'M', 'roma': 'M',
    'shanghai': 'M', 'paris': 'M', 'cincinnati': 'M',
    'canada': 'M', 'montreal': 'M', 'toronto': 'M',
}

def detect_surface_and_level(match_str, sport_key="", sport_title=""):
    """Detect surface and tournament level from match string, sport_key, or sport_title."""
    # Combine all sources for keyword search
    search_str = f"{match_str} {sport_key} {sport_title}".lower()
    surface = 'Hard'  # default
    level = 'A'  # default
    tourney_name = sport_title if sport_title else match_str  # prefer API title

    stuttgart_keys = ('stuttgart', 'boss open', 'porsche tennis grand prix')
    if any(key in search_str for key in stuttgart_keys):
        surface = 'Clay' if any(key in search_str for key in ('wta', 'porsche')) else 'Grass'
        if not sport_title:
            tourney_name = 'Stuttgart'
        return surface, level, tourney_name

    for key, surf in TOURNEY_SURFACE_MAP.items():
        if key in search_str:
            surface = surf
            if not sport_title:
                tourney_name = key.title()
            break

    for key, lvl in TOURNEY_LEVEL_MAP.items():
        if key in search_str:
            level = lvl
            break

    return surface, level, tourney_name


def fuzzy_find_player_id(name, name_to_id, threshold=0.85):
    """Find player ID using fuzzy matching when exact match fails."""
    name_lower = name.lower().strip()
    
    # 1. Exact match
    if name_lower in name_to_id:
        return name_to_id[name_lower]
    
    # 2. Last-name match
    name_parts = name_lower.split()
    last_name = name_parts[-1] if name_parts else name_lower
    
    candidates = []
    for db_name, pid in name_to_id.items():
        db_parts = db_name.split()
        db_last = db_parts[-1] if db_parts else db_name
        
        if db_last == last_name:
            # Last name exact match — check first name similarity
            ratio = SequenceMatcher(None, name_lower, db_name).ratio()
            candidates.append((ratio, db_name, pid))
    
    if candidates:
        candidates.sort(reverse=True)
        if candidates[0][0] >= threshold:
            return candidates[0][2]
    
    # 3. Full fuzzy match (slower, only if last name didn't work)
    best_ratio = 0
    best_id = None
    for db_name, pid in name_to_id.items():
        ratio = SequenceMatcher(None, name_lower, db_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = pid
    
    return best_id if best_ratio >= threshold else None


def _row_text(row, key):
    value = row.get(key, "")
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _players_from_odds_row(row):
    p1_name = _row_text(row, "p1") or _row_text(row, "player_1")
    p2_name = _row_text(row, "p2") or _row_text(row, "player_2")
    if p1_name and p2_name:
        return p1_name, p2_name

    match_str = _row_text(row, "match")
    names_part = match_str.split("] ", 1)[1] if "] " in match_str else match_str
    if " vs " not in names_part:
        return None
    p1_name, p2_name = (part.strip() for part in names_part.split(" vs ", 1))
    return (p1_name, p2_name) if p1_name and p2_name else None


def _json_float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_scan_summary(predictions, generated_at=None, top_n=5):
    """Build a compact live-scan summary for agents and UI surfaces."""
    generated_at = generated_at or datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")

    surface_counts = {}
    confidence_flags = {}
    positive_edges = 0
    low_confidence = 0
    news_adjusted = 0
    coverage_total = 0.0
    coverage_points = 0
    ranked = []

    for pred in predictions:
        surface = str(pred.get("surface") or "Unknown")
        surface_counts[surface] = surface_counts.get(surface, 0) + 1

        flag = pred.get("confidence_flag")
        if flag:
            confidence_flags[flag] = confidence_flags.get(flag, 0) + 1

        if pred.get("low_confidence"):
            low_confidence += 1

        adjustment = pred.get("news_adjustment")
        if isinstance(adjustment, dict) and adjustment.get("applied"):
            news_adjusted += 1

        for key in ("coverage_p1", "coverage_p2"):
            if key in pred:
                coverage_total += _json_float(pred.get(key))
                coverage_points += 1

        edge = _json_float(pred.get("edge"))
        if edge > 0:
            positive_edges += 1

        forensics = pred.get("forensics") or {}
        value_side = int(_json_float(pred.get("value_side"), 0))
        value_player = ""
        if value_side == 1:
            value_player = str(forensics.get("p1_name") or "")
        elif value_side == 2:
            value_player = str(forensics.get("p2_name") or "")

        ranked.append({
            "match": str(pred.get("match") or ""),
            "commence_time": str(pred.get("commence_time") or ""),
            "surface": surface,
            "edge": round(edge, 4),
            "value_side": value_side,
            "value_player": value_player,
            "confidence_flag": flag,
        })

    ranked.sort(key=lambda item: item["edge"], reverse=True)

    return {
        "generated_at": generated_at_iso,
        "match_count": len(predictions),
        "positive_edge_count": positive_edges,
        "low_confidence_count": low_confidence,
        "news_adjusted_count": news_adjusted,
        "average_coverage": round(coverage_total / coverage_points, 3) if coverage_points else 0.0,
        "surface_counts": dict(sorted(surface_counts.items())),
        "confidence_flags": dict(sorted(confidence_flags.items())),
        "top_edges": ranked[:top_n],
    }


def run_inference():
    print("[ML] Running inference on live markets...")
    
    odds_path = PROJECT_ROOT / "data" / "live" / "current_odds.csv"
    if not odds_path.exists():
        print("[ML] ERROR: No market data found.")
        return
        
    df_odds = pd.read_csv(odds_path)
    if df_odds.empty:
        print("[ML] No matches to analyze.")
        return

    # Load unified data for name mapping + rankings
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df_hist = pd.read_csv(unified_path, usecols=['winner_id', 'winner_name', 'loser_id', 'loser_name', 'winner_rank', 'loser_rank', 'tourney_date'])
    
    # Detect most recent match date to handle staleness
    df_hist['tourney_date'] = pd.to_datetime(df_hist['tourney_date'], errors='coerce')
    last_db_date = df_hist['tourney_date'].max()
    print(f"  [ML] Last DB match: {last_db_date.strftime('%Y-%m-%d') if not pd.isna(last_db_date) else 'N/A'}")
    name_to_id = {}
    for _, row in df_hist.drop_duplicates('winner_name').iterrows():
        name_to_id[row['winner_name'].lower()] = str(row['winner_id'])
    for _, row in df_hist.drop_duplicates('loser_name').iterrows():
        name_to_id[row['loser_name'].lower()] = str(row['loser_id'])

    # Build latest-known ranking lookup (most recent match per player)
    id_to_rank = {}
    df_hist_sorted = df_hist.sort_values('tourney_date')
    for _, r in df_hist_sorted.iterrows():
        wid = str(r['winner_id'])
        lid = str(r['loser_id'])
        if pd.notna(r.get('winner_rank')):
            id_to_rank[wid] = float(r['winner_rank'])
        if pd.notna(r.get('loser_rank')):
            id_to_rank[lid] = float(r['loser_rank'])

    # Load clutch stats if available
    clutch_path = PROJECT_ROOT / "data" / "processed" / "player_clutch_stats.csv"
    clutch_lookup = {}
    if clutch_path.exists():
        clutch_df = pd.read_csv(clutch_path)
        clutch_df['date'] = pd.to_datetime(clutch_df['date'], errors='coerce')
        clutch_df = clutch_df.sort_values('date')
        # Keep latest clutch stats per player
        for _, cr in clutch_df.iterrows():
            pid = str(cr.get('player_id', ''))
            if pid:
                clutch_lookup[pid] = {
                    'clutch_bp_saved_pct': cr.get('clutch_bp_saved_pct', 0.6),
                    'clutch_bp_converted_pct': cr.get('clutch_bp_converted_pct', 0.4),
                    'clutch_deuce_win_pct': cr.get('clutch_deuce_win_pct', 0.5),
                    'clutch_tb_win_pct': cr.get('clutch_tb_win_pct', 0.5),
                }

    config, elo_engine, stats_engine, models, scaler, feature_cols, medians = load_resources()
    
    predictions = []
    
    for _, row in df_odds.iterrows():
        match_str = row['match']
        o1 = float(row['odds_1'])
        o2 = float(row['odds_2'])
        
        players = _players_from_odds_row(row)
        if not players:
            continue
        p1_name, p2_name = players
            
        p1_id = fuzzy_find_player_id(p1_name, name_to_id)
        p2_id = fuzzy_find_player_id(p2_name, name_to_id)
        
        # Dynamic surface/level detection from sport_key/sport_title + match string
        sport_key = str(row.get('sport_key', ''))
        sport_title = str(row.get('sport_title', ''))
        surface, tourney_level, tourney_name = detect_surface_and_level(match_str, sport_key, sport_title)
        
        # Adjust match_date to avoid artificial rust if DB is old
        # If DB is more than 30 days old, we pretend today is DB date + 3 days
        real_now = pd.Timestamp.now()
        if not pd.isna(last_db_date) and (real_now - last_db_date).days > 30:
            match_date = last_db_date + pd.Timedelta(days=3)
        else:
            match_date = real_now
        
        p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date) if p1_id else {}
        p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date) if p2_id else {}
        low_confidence = not p1_id or not p2_id or not p1_feats or not p2_feats

        # Coverage score per side — fraction of non-null, non-zero feature values.
        # Drives the prob clamp below (P0-2): unknown players must not yield 90/10 output.
        def _coverage(feats):
            if not feats:
                return 0.0
            vals = [v for v in feats.values() if v is not None]
            if not vals:
                return 0.0
            nonzero = sum(1 for v in vals if v != 0)
            return nonzero / max(len(vals), 1)
        coverage_p1 = _coverage(p1_feats) if p1_id else 0.0
        coverage_p2 = _coverage(p2_feats) if p2_id else 0.0
        
        # Build vector
        input_data = {}
        for k, v in p1_feats.items(): input_data[f"w_{k}"] = v
        for k, v in p2_feats.items(): input_data[f"l_{k}"] = v
        for k in p1_feats:
            if k in p2_feats:
                input_data[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)
        
        # ELO
        w_elo = elo_engine.initial_rating
        l_elo = elo_engine.initial_rating
        w_s_elo = elo_engine.initial_rating
        l_s_elo = elo_engine.initial_rating
        
        if p1_id:
            w_elo = elo_engine.global_ratings.get(p1_id, elo_engine.initial_rating)
            w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
        if p2_id:
            l_elo = elo_engine.global_ratings.get(p2_id, elo_engine.initial_rating)
            l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
            
        input_data["w_elo"] = w_elo
        input_data["l_elo"] = l_elo
        input_data["w_surface_elo"] = w_s_elo
        input_data["l_surface_elo"] = l_s_elo
        input_data["elo_win_prob"] = elo_engine.expected_score(w_s_elo, l_s_elo)
        
        # Market
        margin = (1.0/o1) + (1.0/o2)
        input_data["w_implied_prob"] = (1.0/o1) / margin
        input_data["l_implied_prob"] = (1.0/o2) / margin
        input_data["diff_implied_prob"] = input_data["w_implied_prob"] - input_data["l_implied_prob"]
        
        # Dynamic context based on detected tournament
        input_data["cpi"] = map_cpi(tourney_name, surface)
        level_key = f'level_{tourney_level}'
        for l_key in ['level_G', 'level_M', 'level_A', 'level_C', 'level_S', 'level_F', 'level_D']:
            input_data[l_key] = 1 if l_key == level_key else 0

        # === CONTEXTUAL FEATURES (missing from raw player stats) ===

        # Rankings
        p1_rank = id_to_rank.get(p1_id, 100) if p1_id else 100
        p2_rank = id_to_rank.get(p2_id, 100) if p2_id else 100
        input_data["rank_diff"] = p2_rank - p1_rank  # Positive = P1 ranked higher
        input_data["rank_ratio"] = p2_rank / max(p1_rank, 1)

        # Match context
        input_data["best_of_5"] = 1 if tourney_level == 'G' else 0
        round_map = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7, "RR": 4}
        # Default to R32 (ordinal 3) since we don't know the exact round from odds API
        input_data["round_ordinal"] = 3

        # Competitiveness features
        input_data["abs_elo_prob_diff"] = abs(input_data["elo_win_prob"] - 0.5)
        input_data["abs_implied_prob_diff"] = abs(input_data["diff_implied_prob"])

        # Additive (sum) features for totals prediction
        for w in [10, 20, 50]:
            for stat in ["ace_rate", "bp_save_pct", "avg_total_games", "hold_pct",
                         "tiebreak_rate", "deciding_set_pct"]:
                w_key = f"w_{stat}_{w}"
                l_key = f"l_{stat}_{w}"
                w_val = input_data.get(w_key, 0) or 0
                l_val = input_data.get(l_key, 0) or 0
                input_data[f"sum_{stat}_{w}"] = w_val + l_val
                if stat == "avg_total_games":
                    input_data[f"min_{stat}_{w}"] = min(w_val, l_val) if (w_val and l_val) else 0

        # Clutch features
        p1_clutch = clutch_lookup.get(p1_id, {}) if p1_id else {}
        p2_clutch = clutch_lookup.get(p2_id, {}) if p2_id else {}
        for ckey in ['clutch_bp_saved_pct', 'clutch_bp_converted_pct',
                     'clutch_deuce_win_pct', 'clutch_tb_win_pct']:
            input_data[f"w_{ckey}"] = p1_clutch.get(ckey, medians.get(f"w_{ckey}", 0.5))
            input_data[f"l_{ckey}"] = p2_clutch.get(ckey, medians.get(f"l_{ckey}", 0.5))

        # MLP / Ensembling columns alignment
        X = pd.DataFrame([input_data])
        
        # SMARTER FILLING: Use EXACT training medians for alignment
        for col in feature_cols:
            if col not in X.columns or pd.isna(X.at[0, col]):
                # 1. Try training medians
                if col in medians:
                    X.at[0, col] = medians[col]
                # 2. Hardcoded fallbacks for sanity
                elif any(x in col.lower() for x in ["pct", "win_rate", "win_prob", "prob_"]):
                    X.at[0, col] = 0.5
                elif "days_since_last" in col.lower():
                    X.at[0, col] = 7
                else:
                    X.at[0, col] = 0
                    
        # STALENESS NEUTRALIZATION:
        # Cap raw w_/l_ days_since_last at 90 days (preserves genuine inactivity signal
        # while preventing extreme outliers the model hasn't seen in training).
        # Then RECALCULATE diff_ from the capped values (not cap independently).
        # P1-10: record *raw* pre-cap values so we can surface OOD_LAYOFF to TUI
        # (prevents a 400-day layoff from looking identical to a 90-day one).
        CAP_DAYS = 90
        w_dsl_col = "w_days_since_last"
        l_dsl_col = "l_days_since_last"
        d_dsl_col = "diff_days_since_last"
        raw_w_dsl = float(X.at[0, w_dsl_col]) if w_dsl_col in X.columns else 0.0
        raw_l_dsl = float(X.at[0, l_dsl_col]) if l_dsl_col in X.columns else 0.0
        ood_layoff = max(raw_w_dsl, raw_l_dsl) > CAP_DAYS
        if w_dsl_col in X.columns:
            X.at[0, w_dsl_col] = min(raw_w_dsl, CAP_DAYS)
        if l_dsl_col in X.columns:
            X.at[0, l_dsl_col] = min(raw_l_dsl, CAP_DAYS)
        if d_dsl_col in X.columns and w_dsl_col in X.columns and l_dsl_col in X.columns:
            X.at[0, d_dsl_col] = float(X.at[0, w_dsl_col]) - float(X.at[0, l_dsl_col])
                    
        # Use training medians for any remaining NaNs (not 0, which distorts win_rates)
        for col in feature_cols:
            if col in X.columns and pd.isna(X.at[0, col]):
                X.at[0, col] = medians.get(col, 0)
        # Authoritative column order = the scaler's fit order (the order the scaler AND
        # the models were fitted on). The model-bundle feature_cols may be saved in a
        # different order, which trips scaler.transform's feature-name check; align to
        # the scaler so the scaled vector matches what every model expects.
        order = list(getattr(scaler, "feature_names_in_", feature_cols))
        X = X.reindex(columns=order)
        assert list(X.columns) == order, "Inference column order mismatch"
        if X.isna().any().any():
            missing = X.columns[X.isna().any()].tolist()
            for c in missing:
                X.at[0, c] = medians.get(c, 0)

        # Scaled input
        X_scaled = scaler.transform(X)
        
        # SAFETY CAPPING: Prevent extreme outliers (Z-scores) from breaking the trees
        X_scaled = np.clip(X_scaled, -4, 4)
        
        # 1. Prediction H2H
        prob_1 = float(models['h2h'].predict_proba(X_scaled)[0, 1])
        prob_2 = 1.0 - prob_1

        # P0-2 clamp: when one or both sides have low coverage, shrink confidence
        # toward 0.5 proportionally. Prevents default-propagation (ELO=1500 + medians)
        # from yielding 90/10 on unknown players.
        COVERAGE_THRESHOLD = 0.5
        min_cov = min(coverage_p1, coverage_p2)
        confidence_flag = None
        if low_confidence or min_cov < COVERAGE_THRESHOLD:
            cov_weight = min(min_cov / COVERAGE_THRESHOLD, 1.0)
            prob_1 = 0.5 + (prob_1 - 0.5) * cov_weight
            prob_2 = 1.0 - prob_1
            confidence_flag = "LOW_COVERAGE"
        elif ood_layoff:
            # Layoff exceeds training-seen range. Keep model output (already capped
            # as input) but warn the user — a 400-day absence isn't truly equivalent
            # to a 90-day one, even though the model sees them identically.
            confidence_flag = "OOD_LAYOFF"

        # 2. Prediction Spread (Expected Game Diff P1 - P2)
        exp_game_diff = float(models['spread'].predict(X_scaled)[0])
        
        # 3. Prediction Totals (Expected Total Games)
        exp_total_games = float(models['totals'].predict(X_scaled)[0])
        
        # Edge calculation for both sides (H2H)
        edge_1 = (o1 * prob_1) - 1
        edge_2 = (o2 * prob_2) - 1
        
        # Determine which side has the actual value
        if edge_1 > edge_2:
            best_edge = edge_1
            value_side = 1
        else:
            best_edge = edge_2
            value_side = 2
        
        # Forensic details for TUI
        spread_line = row.get('spread_line', 0)
        spread_o1 = row.get('spread_odds_1', 1.9)
        spread_o2 = row.get('spread_odds_2', 1.9)
        total_line = row.get('total_line', 0)
        total_over = row.get('total_over', 1.9)
        total_under = row.get('total_under', 1.9)

        # Determine spread/totals edge indicators
        spread_edge_label = None
        if spread_line != 0 and exp_game_diff != 0:
            if exp_game_diff > spread_line + 1.0:
                spread_edge_label = "P1"
            elif exp_game_diff < spread_line - 1.0:
                spread_edge_label = "P2"

        totals_edge_label = None
        if total_line > 0 and exp_total_games > 0:
            if exp_total_games > total_line + 0.5:
                totals_edge_label = "OVER"
            elif exp_total_games < total_line - 0.5:
                totals_edge_label = "UNDER"

        forensics = {
            "p1_id": p1_id,
            "p2_id": p2_id,
            "p1_name": p1_name,
            "p2_name": p2_name,
            "value_side": value_side,
            "surface": surface,
            "tourney_name": tourney_name,
            "tourney_level": tourney_level,
            "p1_rank": int(p1_rank),
            "p2_rank": int(p2_rank),
            "exp_game_diff": round(exp_game_diff, 1),
            "exp_total_games": round(exp_total_games, 1),
            "market_spread": float(spread_line) if spread_line else 0.0,
            "market_total": float(total_line) if total_line else 0.0,
            "spread_odds_1": float(spread_o1),
            "spread_odds_2": float(spread_o2),
            "total_over_odds": float(total_over),
            "total_under_odds": float(total_under),
            "spread_edge": spread_edge_label,
            "totals_edge": totals_edge_label,
            "p1_elo": round(w_elo),
            "p2_elo": round(l_elo),
            "p1_surface_elo": round(w_s_elo),
            "p2_surface_elo": round(l_s_elo),
            "p1_form": f"{p1_feats.get('win_rate_10', 0):.0%}" if p1_id else "N/A",
            "p2_form": f"{p2_feats.get('win_rate_10', 0):.0%}" if p2_id else "N/A",
            "p1_h2h": p1_feats.get('h2h_wins', 0) if p1_id else 0,
            "p2_h2h": p1_feats.get('h2h_losses', 0) if p1_id else 0,
        }
        
        predictions.append({
            "match": match_str,
            "commence_time": str(row.get('commence_time', '')),
            "surface": surface,
            "odds_1": float(o1),
            "odds_2": float(o2),
            "prob_1": float(prob_1),
            "prob_2": float(prob_2),
            "exp_game_diff": float(exp_game_diff),
            "exp_total_games": float(exp_total_games),
            "market_spread": float(spread_line) if spread_line else 0.0,
            "market_total": float(total_line) if total_line else 0.0,
            "spread_odds_1": float(spread_o1),
            "spread_odds_2": float(spread_o2),
            "total_over_odds": float(total_over),
            "total_under_odds": float(total_under),
            "edge": float(best_edge),
            "value_side": int(value_side),
            "low_confidence": bool(low_confidence),
            "confidence_flag": confidence_flag,
            "coverage_p1": round(coverage_p1, 3),
            "coverage_p2": round(coverage_p2, 3),
            "forensics": forensics
        })

    # Agentic Research (v2.0) — ReAct agent with tool-use
    # Fallback to old passive pipeline if agentic produces 0 adjustments.
    news_applied = False
    try:
        from src.live.agentic_research import run_agentic_research
        predictions = run_agentic_research(predictions)
        news_applied = any(
            p.get("news_adjustment", {}).get("applied")
            for p in predictions
        )
    except Exception as e:
        print(f"  [Agent] WARNING: Agentic research failed: {e}")

    if not news_applied:
        print(f"  [Agent] No adjustments applied — trying passive news fallback...")
        try:
            from src.live.news_adjustment import run_news_adjustment
            predictions = run_news_adjustment(predictions)
        except Exception as e2:
            print(f"  [News] WARNING: Fallback news adjustment also skipped: {e2}")

    # Save to JSON for TUI (ensure all numpy types are converted)
    with open(PROJECT_ROOT / "data" / "live" / "predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, default=lambda x: float(x) if hasattr(x, 'item') else str(x))

    summary = build_scan_summary(predictions)
    with open(PROJECT_ROOT / "data" / "live" / "scan_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Auto-log decisions to BetAnalytix DB
    try:
        from src.betting.portfolio import BetAnalytix
        db = BetAnalytix()
        scan_id = db.log_decisions(predictions)
        db.close()
        print(f"[DB] Logged {len(predictions)} decisions to BetAnalytix [{scan_id}]")
    except Exception as e:
        print(f"[DB] WARNING: BetAnalytix logging failed: {e}")

    print(f"[ML] Inference complete for {len(predictions)} matches.")

if __name__ == "__main__":
    run_inference()
