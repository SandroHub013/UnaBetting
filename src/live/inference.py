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


def _value_player(pred, value_side):
    """Name of the side the model likes, if it picked one."""
    forensics = pred.get("forensics") or {}
    if value_side == 1:
        return str(forensics.get("p1_name") or "")
    if value_side == 2:
        return str(forensics.get("p2_name") or "")
    return ""


class _ScanTally:
    """Running counts over a scan, plus the ranked row for each prediction."""

    def __init__(self):
        self.surface_counts = {}
        self.confidence_flags = {}
        self.positive_edges = 0
        self.low_confidence = 0
        self.news_adjusted = 0
        self._coverage_total = 0.0
        self._coverage_points = 0

    def add(self, pred):
        surface = str(pred.get("surface") or "Unknown")
        self.surface_counts[surface] = self.surface_counts.get(surface, 0) + 1

        flag = pred.get("confidence_flag")
        if flag:
            self.confidence_flags[flag] = self.confidence_flags.get(flag, 0) + 1
        if pred.get("low_confidence"):
            self.low_confidence += 1

        adjustment = pred.get("news_adjustment")
        if isinstance(adjustment, dict) and adjustment.get("applied"):
            self.news_adjusted += 1

        for key in ("coverage_p1", "coverage_p2"):
            if key in pred:
                self._coverage_total += _json_float(pred.get(key))
                self._coverage_points += 1

        edge = _json_float(pred.get("edge"))
        if edge > 0:
            self.positive_edges += 1

        value_side = int(_json_float(pred.get("value_side"), 0))
        return {
            "match": str(pred.get("match") or ""),
            "commence_time": str(pred.get("commence_time") or ""),
            "surface": surface,
            "edge": round(edge, 4),
            "value_side": value_side,
            "value_player": _value_player(pred, value_side),
            "confidence_flag": flag,
        }

    def average_coverage(self):
        if not self._coverage_points:
            return 0.0
        return round(self._coverage_total / self._coverage_points, 3)


def build_scan_summary(predictions, generated_at=None, top_n=5):
    """Build a compact live-scan summary for agents and UI surfaces."""
    generated_at = generated_at or datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")

    tally = _ScanTally()
    ranked = [tally.add(pred) for pred in predictions]
    ranked.sort(key=lambda item: item["edge"], reverse=True)

    return {
        "generated_at": generated_at_iso,
        "match_count": len(predictions),
        "positive_edge_count": tally.positive_edges,
        "low_confidence_count": tally.low_confidence,
        "news_adjusted_count": tally.news_adjusted,
        "average_coverage": tally.average_coverage(),
        "surface_counts": dict(sorted(tally.surface_counts.items())),
        "confidence_flags": dict(sorted(tally.confidence_flags.items())),
        "top_edges": ranked[:top_n],
    }


#: rolling windows the totals sums are built over
_ROLL_WINDOWS = (10, 20, 50)
_TOTALS_SUMS = ("ace_rate", "bp_save_pct", "avg_total_games", "hold_pct",
                "tiebreak_rate", "deciding_set_pct")
_CLUTCH_KEYS = ("clutch_bp_saved_pct", "clutch_bp_converted_pct",
                "clutch_deuce_win_pct", "clutch_tb_win_pct")
_LEVEL_KEYS = ("level_G", "level_M", "level_A", "level_C",
               "level_S", "level_F", "level_D")

#: layoffs beyond this many days sit outside the range the model was trained on
CAP_DAYS = 90
#: below this share of known features, shrink the model's confidence toward 0.5
COVERAGE_THRESHOLD = 0.5


def _load_history():
    """Name->id and id->latest rank lookups, plus the newest match date on file."""
    unified_path = PROJECT_ROOT / "data" / "processed" / "atp_unified.csv"
    df_hist = pd.read_csv(unified_path, usecols=[
        'winner_id', 'winner_name', 'loser_id', 'loser_name',
        'winner_rank', 'loser_rank', 'tourney_date'])
    df_hist['tourney_date'] = pd.to_datetime(df_hist['tourney_date'], errors='coerce')
    last_db_date = df_hist['tourney_date'].max()
    print(f"  [ML] Last DB match: "
          f"{last_db_date.strftime('%Y-%m-%d') if not pd.isna(last_db_date) else 'N/A'}")

    name_to_id = {}
    for _, row in df_hist.drop_duplicates('winner_name').iterrows():
        name_to_id[row['winner_name'].lower()] = str(row['winner_id'])
    for _, row in df_hist.drop_duplicates('loser_name').iterrows():
        name_to_id[row['loser_name'].lower()] = str(row['loser_id'])

    id_to_rank = {}
    for _, r in df_hist.sort_values('tourney_date').iterrows():
        if pd.notna(r.get('winner_rank')):
            id_to_rank[str(r['winner_id'])] = float(r['winner_rank'])
        if pd.notna(r.get('loser_rank')):
            id_to_rank[str(r['loser_id'])] = float(r['loser_rank'])

    return name_to_id, id_to_rank, last_db_date


def _load_clutch_lookup():
    """Latest clutch stats per player, empty when the file has not been built."""
    clutch_path = PROJECT_ROOT / "data" / "processed" / "player_clutch_stats.csv"
    lookup = {}
    if not clutch_path.exists():
        return lookup
    clutch_df = pd.read_csv(clutch_path)
    clutch_df['date'] = pd.to_datetime(clutch_df['date'], errors='coerce')
    for _, cr in clutch_df.sort_values('date').iterrows():
        pid = str(cr.get('player_id', ''))
        if pid:
            lookup[pid] = {
                'clutch_bp_saved_pct': cr.get('clutch_bp_saved_pct', 0.6),
                'clutch_bp_converted_pct': cr.get('clutch_bp_converted_pct', 0.4),
                'clutch_deuce_win_pct': cr.get('clutch_deuce_win_pct', 0.5),
                'clutch_tb_win_pct': cr.get('clutch_tb_win_pct', 0.5),
            }
    return lookup


def _coverage(feats):
    """Share of a player's features that are known and non-zero."""
    if not feats:
        return 0.0
    vals = [v for v in feats.values() if v is not None]
    if not vals:
        return 0.0
    return sum(1 for v in vals if v != 0) / max(len(vals), 1)


def _effective_match_date(last_db_date):
    """A stale database would otherwise read as weeks of rust for everyone."""
    real_now = pd.Timestamp.now()
    if not pd.isna(last_db_date) and (real_now - last_db_date).days > 30:
        return last_db_date + pd.Timedelta(days=3)
    return real_now


def _player_features_block(p1_feats, p2_feats):
    block = {}
    for k, v in p1_feats.items():
        block[f"w_{k}"] = v
    for k, v in p2_feats.items():
        block[f"l_{k}"] = v
    for k in p1_feats:
        if k in p2_feats:
            block[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)
    return block


def _elo_values(elo_engine, p1_id, p2_id, surface):
    """(global, surface) ELO for both players, defaulting to the initial rating."""
    initial = elo_engine.initial_rating
    w_elo = w_s_elo = l_elo = l_s_elo = initial
    if p1_id:
        w_elo = elo_engine.global_ratings.get(p1_id, initial)
        w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
    if p2_id:
        l_elo = elo_engine.global_ratings.get(p2_id, initial)
        l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
    return w_elo, l_elo, w_s_elo, l_s_elo


def _market_block(o1, o2):
    margin = (1.0 / o1) + (1.0 / o2)
    w_implied = (1.0 / o1) / margin
    l_implied = (1.0 / o2) / margin
    return {"w_implied_prob": w_implied, "l_implied_prob": l_implied,
            "diff_implied_prob": w_implied - l_implied}


def _context_block(tourney_name, tourney_level, surface, p1_rank, p2_rank):
    block = {"cpi": map_cpi(tourney_name, surface)}
    level_key = f"level_{tourney_level}"
    for l_key in _LEVEL_KEYS:
        block[l_key] = 1 if l_key == level_key else 0
    block["rank_diff"] = p2_rank - p1_rank  # positive = P1 ranked higher
    block["rank_ratio"] = p2_rank / max(p1_rank, 1)
    block["best_of_5"] = 1 if tourney_level == 'G' else 0
    # the odds API does not tell us the round; R32 is the median draw position
    block["round_ordinal"] = 3
    return block


def _add_totals_sums(input_data):
    for w in _ROLL_WINDOWS:
        for stat in _TOTALS_SUMS:
            w_val = input_data.get(f"w_{stat}_{w}", 0) or 0
            l_val = input_data.get(f"l_{stat}_{w}", 0) or 0
            input_data[f"sum_{stat}_{w}"] = w_val + l_val
            if stat == "avg_total_games":
                input_data[f"min_{stat}_{w}"] = min(w_val, l_val) if (w_val and l_val) else 0


def _clutch_block(clutch_lookup, p1_id, p2_id, medians):
    p1_clutch = clutch_lookup.get(p1_id, {}) if p1_id else {}
    p2_clutch = clutch_lookup.get(p2_id, {}) if p2_id else {}
    block = {}
    for ckey in _CLUTCH_KEYS:
        block[f"w_{ckey}"] = p1_clutch.get(ckey, medians.get(f"w_{ckey}", 0.5))
        block[f"l_{ckey}"] = p2_clutch.get(ckey, medians.get(f"l_{ckey}", 0.5))
    return block


def _fill_missing(X, feature_cols, medians):
    """Training medians first, then sane per-family fallbacks."""
    for col in feature_cols:
        if col in X.columns and not pd.isna(X.at[0, col]):
            continue
        if col in medians:
            X.at[0, col] = medians[col]
        elif any(x in col.lower() for x in ["pct", "win_rate", "win_prob", "prob_"]):
            X.at[0, col] = 0.5
        elif "days_since_last" in col.lower():
            X.at[0, col] = 7
        else:
            X.at[0, col] = 0


def _neutralise_staleness(X):
    """Cap the layoff columns and recompute their diff from the capped values.

    Capping preserves a genuine inactivity signal while keeping the model inside
    the range it saw in training. The raw values are read first so a 400-day
    absence can still be flagged instead of looking like a 90-day one.
    """
    w_col, l_col, d_col = "w_days_since_last", "l_days_since_last", "diff_days_since_last"
    raw_w = float(X.at[0, w_col]) if w_col in X.columns else 0.0
    raw_l = float(X.at[0, l_col]) if l_col in X.columns else 0.0
    if w_col in X.columns:
        X.at[0, w_col] = min(raw_w, CAP_DAYS)
    if l_col in X.columns:
        X.at[0, l_col] = min(raw_l, CAP_DAYS)
    if d_col in X.columns and w_col in X.columns and l_col in X.columns:
        X.at[0, d_col] = float(X.at[0, w_col]) - float(X.at[0, l_col])
    return max(raw_w, raw_l) > CAP_DAYS


def _align_columns(X, feature_cols, medians, scaler):
    """Reindex to the scaler's fit order — the order every model expects.

    The model bundle's feature_cols may be stored in a different order, which
    trips scaler.transform's feature-name check.
    """
    for col in feature_cols:
        if col in X.columns and pd.isna(X.at[0, col]):
            X.at[0, col] = medians.get(col, 0)
    order = list(getattr(scaler, "feature_names_in_", feature_cols))
    X = X.reindex(columns=order)
    assert list(X.columns) == order, "Inference column order mismatch"
    if X.isna().any().any():
        for c in X.columns[X.isna().any()].tolist():
            X.at[0, c] = medians.get(c, 0)
    return X


def _clamp_for_coverage(prob_1, low_confidence, coverage_p1, coverage_p2, ood_layoff):
    """Shrink toward 0.5 when a player is barely known; flag a long layoff.

    Without this, default propagation (ELO 1500 plus medians) yields 90/10 on
    players the engine has never seen.
    """
    min_cov = min(coverage_p1, coverage_p2)
    if low_confidence or min_cov < COVERAGE_THRESHOLD:
        cov_weight = min(min_cov / COVERAGE_THRESHOLD, 1.0)
        return 0.5 + (prob_1 - 0.5) * cov_weight, "LOW_COVERAGE"
    if ood_layoff:
        # the model was fed the capped value, so warn rather than adjust
        return prob_1, "OOD_LAYOFF"
    return prob_1, None


def _spread_edge_label(exp_game_diff, spread_line):
    if spread_line == 0 or exp_game_diff == 0:
        return None
    if exp_game_diff > spread_line + 1.0:
        return "P1"
    return "P2" if exp_game_diff < spread_line - 1.0 else None


def _totals_edge_label(exp_total_games, total_line):
    if total_line <= 0 or exp_total_games <= 0:
        return None
    if exp_total_games > total_line + 0.5:
        return "OVER"
    return "UNDER" if exp_total_games < total_line - 0.5 else None


def _build_feature_row(ctx):
    """Every model input for one match, before alignment and scaling."""
    input_data = _player_features_block(ctx["p1_feats"], ctx["p2_feats"])
    w_elo, l_elo, w_s_elo, l_s_elo = ctx["elos"]
    input_data["w_elo"] = w_elo
    input_data["l_elo"] = l_elo
    input_data["w_surface_elo"] = w_s_elo
    input_data["l_surface_elo"] = l_s_elo
    input_data["elo_win_prob"] = ctx["elo_engine"].expected_score(w_s_elo, l_s_elo)
    input_data.update(_market_block(ctx["o1"], ctx["o2"]))
    input_data.update(_context_block(ctx["tourney_name"], ctx["tourney_level"],
                                     ctx["surface"], ctx["p1_rank"], ctx["p2_rank"]))
    input_data["abs_elo_prob_diff"] = abs(input_data["elo_win_prob"] - 0.5)
    input_data["abs_implied_prob_diff"] = abs(input_data["diff_implied_prob"])
    _add_totals_sums(input_data)
    input_data.update(_clutch_block(ctx["clutch_lookup"], ctx["p1_id"], ctx["p2_id"],
                                    ctx["medians"]))
    return input_data


def _forensics(ctx, market, exp_game_diff, exp_total_games, value_side):
    p1_feats, p2_feats = ctx["p1_feats"], ctx["p2_feats"]
    w_elo, l_elo, w_s_elo, l_s_elo = ctx["elos"]
    return {
        "p1_id": ctx["p1_id"],
        "p2_id": ctx["p2_id"],
        "p1_name": ctx["p1_name"],
        "p2_name": ctx["p2_name"],
        "value_side": value_side,
        "surface": ctx["surface"],
        "tourney_name": ctx["tourney_name"],
        "tourney_level": ctx["tourney_level"],
        "p1_rank": int(ctx["p1_rank"]),
        "p2_rank": int(ctx["p2_rank"]),
        "exp_game_diff": round(exp_game_diff, 1),
        "exp_total_games": round(exp_total_games, 1),
        "market_spread": float(market["spread_line"]) if market["spread_line"] else 0.0,
        "market_total": float(market["total_line"]) if market["total_line"] else 0.0,
        "spread_odds_1": float(market["spread_o1"]),
        "spread_odds_2": float(market["spread_o2"]),
        "total_over_odds": float(market["total_over"]),
        "total_under_odds": float(market["total_under"]),
        "spread_edge": _spread_edge_label(exp_game_diff, market["spread_line"]),
        "totals_edge": _totals_edge_label(exp_total_games, market["total_line"]),
        "p1_elo": round(w_elo),
        "p2_elo": round(l_elo),
        "p1_surface_elo": round(w_s_elo),
        "p2_surface_elo": round(l_s_elo),
        "p1_form": f"{p1_feats.get('win_rate_10', 0):.0%}" if ctx["p1_id"] else "N/A",
        "p2_form": f"{p2_feats.get('win_rate_10', 0):.0%}" if ctx["p2_id"] else "N/A",
        "p1_h2h": p1_feats.get('h2h_wins', 0) if ctx["p1_id"] else 0,
        "p2_h2h": p1_feats.get('h2h_losses', 0) if ctx["p1_id"] else 0,
    }


def _market_lines(row):
    return {
        "spread_line": row.get('spread_line', 0),
        "spread_o1": row.get('spread_odds_1', 1.9),
        "spread_o2": row.get('spread_odds_2', 1.9),
        "total_line": row.get('total_line', 0),
        "total_over": row.get('total_over', 1.9),
        "total_under": row.get('total_under', 1.9),
    }


def _match_context(row, resources, lookups):
    """Everything one match needs, or None when neither player can be identified."""
    players = _players_from_odds_row(row)
    if not players:
        return None
    p1_name, p2_name = players
    name_to_id, id_to_rank, last_db_date, clutch_lookup = lookups
    elo_engine, stats_engine, medians = resources

    p1_id = fuzzy_find_player_id(p1_name, name_to_id)
    p2_id = fuzzy_find_player_id(p2_name, name_to_id)
    surface, tourney_level, tourney_name = detect_surface_and_level(
        row['match'], str(row.get('sport_key', '')), str(row.get('sport_title', '')))
    match_date = _effective_match_date(last_db_date)

    p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date) if p1_id else {}
    p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date) if p2_id else {}
    return {
        "p1_name": p1_name, "p2_name": p2_name,
        "p1_id": p1_id, "p2_id": p2_id,
        "p1_feats": p1_feats, "p2_feats": p2_feats,
        "low_confidence": not p1_id or not p2_id or not p1_feats or not p2_feats,
        "coverage_p1": _coverage(p1_feats) if p1_id else 0.0,
        "coverage_p2": _coverage(p2_feats) if p2_id else 0.0,
        "surface": surface, "tourney_level": tourney_level, "tourney_name": tourney_name,
        "o1": float(row['odds_1']), "o2": float(row['odds_2']),
        "p1_rank": id_to_rank.get(p1_id, 100) if p1_id else 100,
        "p2_rank": id_to_rank.get(p2_id, 100) if p2_id else 100,
        "elo_engine": elo_engine,
        "elos": _elo_values(elo_engine, p1_id, p2_id, surface),
        "clutch_lookup": clutch_lookup,
        "medians": medians,
    }


def _predict_match(row, ctx, models, scaler, feature_cols, medians):
    """Model output plus market comparison for one match."""
    X = pd.DataFrame([_build_feature_row(ctx)])
    _fill_missing(X, feature_cols, medians)
    ood_layoff = _neutralise_staleness(X)
    X = _align_columns(X, feature_cols, medians, scaler)

    # cap the scaled vector so an extreme z-score cannot break the trees
    x_scaled = np.clip(scaler.transform(X), -4, 4)

    prob_1 = float(models['h2h'].predict_proba(x_scaled)[0, 1])
    prob_1, confidence_flag = _clamp_for_coverage(
        prob_1, ctx["low_confidence"], ctx["coverage_p1"], ctx["coverage_p2"], ood_layoff)
    prob_2 = 1.0 - prob_1

    exp_game_diff = float(models['spread'].predict(x_scaled)[0])
    exp_total_games = float(models['totals'].predict(x_scaled)[0])

    o1, o2 = ctx["o1"], ctx["o2"]
    edge_1 = (o1 * prob_1) - 1
    edge_2 = (o2 * prob_2) - 1
    best_edge, value_side = (edge_1, 1) if edge_1 > edge_2 else (edge_2, 2)

    market = _market_lines(row)
    return {
        "match": row['match'],
        "commence_time": str(row.get('commence_time', '')),
        "surface": ctx["surface"],
        "odds_1": float(o1),
        "odds_2": float(o2),
        "prob_1": float(prob_1),
        "prob_2": float(prob_2),
        "exp_game_diff": float(exp_game_diff),
        "exp_total_games": float(exp_total_games),
        "market_spread": float(market["spread_line"]) if market["spread_line"] else 0.0,
        "market_total": float(market["total_line"]) if market["total_line"] else 0.0,
        "spread_odds_1": float(market["spread_o1"]),
        "spread_odds_2": float(market["spread_o2"]),
        "total_over_odds": float(market["total_over"]),
        "total_under_odds": float(market["total_under"]),
        "edge": float(best_edge),
        "value_side": int(value_side),
        "low_confidence": bool(ctx["low_confidence"]),
        "confidence_flag": confidence_flag,
        "coverage_p1": round(ctx["coverage_p1"], 3),
        "coverage_p2": round(ctx["coverage_p2"], 3),
        "forensics": _forensics(ctx, market, exp_game_diff, exp_total_games, value_side),
    }


def _apply_news(predictions):
    """ReAct agent first; fall back to the passive pipeline if it adjusts nothing."""
    news_applied = False
    try:
        from src.live.agentic_research import run_agentic_research
        predictions = run_agentic_research(predictions)
        news_applied = any(p.get("news_adjustment", {}).get("applied") for p in predictions)
    except Exception as e:
        print(f"  [Agent] WARNING: Agentic research failed: {e}")

    if not news_applied:
        print("  [Agent] No adjustments applied — trying passive news fallback...")
        try:
            from src.live.news_adjustment import run_news_adjustment
            predictions = run_news_adjustment(predictions)
        except Exception as e2:
            print(f"  [News] WARNING: Fallback news adjustment also skipped: {e2}")
    return predictions


def _persist(predictions):
    live_dir = PROJECT_ROOT / "data" / "live"
    with open(live_dir / "predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2,
                  default=lambda x: float(x) if hasattr(x, 'item') else str(x))
    with open(live_dir / "scan_summary.json", "w", encoding="utf-8") as f:
        json.dump(build_scan_summary(predictions), f, indent=2)

    try:
        from src.betting.portfolio import BetAnalytix
        db = BetAnalytix()
        scan_id = db.log_decisions(predictions)
        db.close()
        print(f"[DB] Logged {len(predictions)} decisions to BetAnalytix [{scan_id}]")
    except Exception as e:
        print(f"[DB] WARNING: BetAnalytix logging failed: {e}")


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

    name_to_id, id_to_rank, last_db_date = _load_history()
    clutch_lookup = _load_clutch_lookup()
    _config, elo_engine, stats_engine, models, scaler, feature_cols, medians = load_resources()

    resources = (elo_engine, stats_engine, medians)
    lookups = (name_to_id, id_to_rank, last_db_date, clutch_lookup)

    predictions = []
    for _, row in df_odds.iterrows():
        ctx = _match_context(row, resources, lookups)
        if ctx is None:
            continue
        predictions.append(
            _predict_match(row, ctx, models, scaler, feature_cols, medians))

    predictions = _apply_news(predictions)
    _persist(predictions)
    print(f"[ML] Inference complete for {len(predictions)} matches.")


if __name__ == "__main__":
    run_inference()
