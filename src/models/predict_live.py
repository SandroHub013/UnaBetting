
import pandas as pd
import joblib
import yaml
from src.features.player_stats import PlayerStatsEngine
from src.features.elo import EloRating
from src.features.sota_features import map_cpi

from src.runtime_paths import DATA_ROOT as PROJECT_ROOT  # writable+seeded root (repo root in dev)

def load_resources(tour="atp"):
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    scaler_path = PROJECT_ROOT / config["paths"]["models"] / f"{tour}_scaler.pkl"
    features_meta_path = PROJECT_ROOT / config["paths"]["models"] / f"{tour}_features.txt"
    medians_path = PROJECT_ROOT / config["paths"]["models"] / f"{tour}_medians.pkl"

    scaler = joblib.load(scaler_path)
    medians = joblib.load(medians_path) if medians_path.exists() else {}

    with open(features_meta_path, "r") as f:
        feature_cols = [line.strip() for line in f if line.strip()]

    return config, scaler, feature_cols, medians

def get_player_id(name, df):
    """Try to find player ID from name."""
    match = df[df['winner_name'].str.contains(name, case=False, na=False)]
    if not match.empty:
        return match.iloc[0]['winner_id']
    match = df[df['loser_name'].str.contains(name, case=False, na=False)]
    if not match.empty:
        return match.iloc[0]['loser_id']
    return None

_LEVEL_KEYS = ("level_G", "level_M", "level_A", "level_C",
               "level_S", "level_F", "level_D")


def _populate_engines(df):
    """Replay the whole history into fresh ELO and stats engines.

    Slow for a live script; production would persist the engine state instead.
    """
    elo_engine = EloRating()
    stats_engine = PlayerStatsEngine()  # windows (10/20/50) are fixed inside the engine
    print("  ⏳ Popolamento motori statistici (può richiedere un minuto)...")
    elo_engine.process_matches(df)
    for _, row in df.iterrows():
        stats_engine.record_match(row, is_winner=True)
        stats_engine.record_match(row, is_winner=False)
    return elo_engine, stats_engine


def _elo_block(elo_engine, p1_id, p2_id, surface):
    if not (p1_id and p2_id):
        return {"elo_win_prob": 0.5}  # baseline for an unknown pairing
    w_s_elo = elo_engine.get_combined_rating(p1_id, surface)
    l_s_elo = elo_engine.get_combined_rating(p2_id, surface)
    return {
        "w_elo": elo_engine.global_ratings[p1_id],
        "l_elo": elo_engine.global_ratings[p2_id],
        "w_surface_elo": w_s_elo,
        "l_surface_elo": l_s_elo,
        "elo_win_prob": elo_engine.expected_score(w_s_elo, l_s_elo),
    }


def _odds_block(odds_p1, odds_p2):
    """Implied probabilities and the model segment they select."""
    if not (odds_p1 and odds_p2):
        return {"w_implied_prob": 0, "l_implied_prob": 0,
                "diff_implied_prob": 0, "has_odds": 0}, "blind"
    margin = (1.0 / odds_p1) + (1.0 / odds_p2)
    w = (1.0 / odds_p1) / margin
    l = (1.0 / odds_p2) / margin
    return {"w_implied_prob": w, "l_implied_prob": l,
            "diff_implied_prob": w - l, "has_odds": 1}, "odds"


def _build_input(p1_feats, p2_feats, elo_engine, p1_id, p2_id,
                 surface, tourney_name, tourney_level, odds_p1, odds_p2):
    input_data = {}
    for k, v in p1_feats.items():
        input_data[f"w_{k}"] = v
    for k, v in p2_feats.items():
        input_data[f"l_{k}"] = v
    for k in p1_feats:
        if k in p2_feats:
            input_data[f"diff_{k}"] = (p1_feats[k] or 0) - (p2_feats[k] or 0)

    input_data.update(_elo_block(elo_engine, p1_id, p2_id, surface))
    odds_features, segment = _odds_block(odds_p1, odds_p2)
    input_data.update(odds_features)

    input_data["cpi"] = map_cpi(tourney_name, surface)
    level_map = {'G': 'level_G', 'M': 'level_M', 'A': 'level_A'}
    for l_key in _LEVEL_KEYS:
        input_data[l_key] = 1 if level_map.get(tourney_level) == l_key else 0
    return input_data, segment


def _align(input_data, feature_cols, medians):
    """Model matrix in training order, missing values filled from the medians."""
    x_live = pd.DataFrame([input_data])
    for col in feature_cols:
        if col not in x_live.columns:
            x_live[col] = 0
    x_live = x_live[feature_cols]
    for col in feature_cols:
        if pd.isna(x_live.at[0, col]):
            default = 0.5 if ('rate' in col or 'pct' in col or 'prob' in col) else 0
            x_live.at[0, col] = medians.get(col, default)
    return x_live


def _load_segment_models(config, tour, segment):
    """The three ensembles for this segment, or None if any is missing."""
    models = {}
    for target in ["target", "game_diff", "total_games"]:
        model_path = PROJECT_ROOT / config["paths"]["models"] / f"{tour}_{target}_{segment}_ensemble.pkl"
        if not model_path.exists():
            print(f"⚠️ Modello ensemble per {target} ({segment}) non trovato! in {model_path}")
            return None
        model_data = joblib.load(model_path)
        models[target] = (model_data["model"]
                          if isinstance(model_data, dict) and "model" in model_data
                          else model_data)
    return models


def _report(p1_name, p2_name, prob_p1, prob_p2, odds_p1, odds_p2, segment):
    print("\n" + "=" * 40)
    print(f"🎯 PREDIZIONE: {p1_name} vs {p2_name}")
    print("=" * 40)
    print(f"📊 Probabilità {p1_name}: {prob_p1:.2%}")
    print(f"📊 Probabilità {p2_name}: {prob_p2:.2%}")

    if not (odds_p1 and odds_p2):
        print(f"\n📊 Nessuna quota fornita. Modello utilizzato: {segment.upper()}")
        return

    fair_odds_p1 = 1.0 / prob_p1
    fair_odds_p2 = 1.0 / prob_p2
    print(f"\n💰 Quote Bet365: {odds_p1} / {odds_p2}")
    print(f"📉 Quote Fair:   {fair_odds_p1:.2f} / {fair_odds_p2:.2f}")

    if odds_p1 > fair_odds_p1:
        print(f"✅ VALUE BET su {p1_name}! (Edge: {(odds_p1 / fair_odds_p1) - 1:.2%})")
    elif odds_p2 > fair_odds_p2:
        print(f"✅ VALUE BET su {p2_name}! (Edge: {(odds_p2 / fair_odds_p2) - 1:.2%})")
    else:
        print("❌ Nessun valore trovato.")


def predict_match(p1_name, p2_name, tourney_name, surface, tourney_level,
                  odds_p1=None, odds_p2=None, tour="atp"):
    config, scaler, feature_cols, medians = load_resources(tour=tour)

    unified_path = PROJECT_ROOT / "data" / "processed" / f"{tour}_unified.csv"
    df = pd.read_csv(unified_path, low_memory=False)
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])  # CRITICAL: parse dates
    df = df.sort_values('tourney_date')

    p1_id = get_player_id(p1_name, df)
    p2_id = get_player_id(p2_name, df)
    print(f"\n🔍 Analisi Match: {p1_name} (ID: {p1_id}) vs {p2_name} (ID: {p2_id})")

    elo_engine, stats_engine = _populate_engines(df)

    match_date = pd.Timestamp.now()
    p1_feats = stats_engine.get_player_features(p1_id, surface, p2_id, match_date) if p1_id else {}
    p2_feats = stats_engine.get_player_features(p2_id, surface, p1_id, match_date) if p2_id else {}

    input_data, segment = _build_input(
        p1_feats, p2_feats, elo_engine, p1_id, p2_id,
        surface, tourney_name, tourney_level, odds_p1, odds_p2)
    x_live = _align(input_data, feature_cols, medians)

    models = _load_segment_models(config, tour, segment)
    if models is None:
        return

    x_scaled = scaler.transform(x_live)
    prob_p1 = models["target"].predict_proba(x_scaled)[0, 1]
    _report(p1_name, p2_name, prob_p1, 1 - prob_p1, odds_p1, odds_p2, segment)


if __name__ == "__main__":
    # Test con i dati estratti dall'utente
    predict_match(
        p1_name="Learner Tien",
        p2_name="Davidovich Fokina",
        tourney_name="Indian Wells Masters",
        surface="Hard",
        tourney_level="M",
        odds_p1=2.37,
        odds_p2=1.57
    )
