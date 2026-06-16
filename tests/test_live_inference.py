"""
Smoke test for the live inference load_resources() function.

This test guards against the class of breakage where model artifacts change
format (legacy bare pickle vs bundle dict) or the return tuple shape changes.
"""
from datetime import datetime, timezone

import pytest

from src.live.inference import (
    _players_from_odds_row,
    build_scan_summary,
    detect_surface_and_level,
)


def test_players_from_odds_row_prefers_structured_names():
    row = {
        "match": "[12:00] Wrong Name vs Bad Name",
        "p1": "Carlos Alcaraz",
        "p2": "Jannik Sinner",
    }

    assert _players_from_odds_row(row) == ("Carlos Alcaraz", "Jannik Sinner")


def test_players_from_odds_row_parses_legacy_match_string():
    row = {"match": "[12:00] Carlos Alcaraz vs Jannik Sinner"}

    assert _players_from_odds_row(row) == ("Carlos Alcaraz", "Jannik Sinner")


def test_detect_surface_handles_stuttgart_tour_context():
    assert detect_surface_and_level("", sport_title="ATP Stuttgart")[0] == "Grass"
    assert detect_surface_and_level("", sport_title="BOSS OPEN")[0] == "Grass"
    assert detect_surface_and_level("", sport_title="Porsche Tennis Grand Prix")[0] == "Clay"


def test_build_scan_summary_counts_edges_and_confidence_flags():
    predictions = [
        {
            "match": "[12:00] Alpha vs Beta",
            "commence_time": "2026-06-17T12:00:00",
            "surface": "Grass",
            "edge": 0.08,
            "value_side": 1,
            "low_confidence": False,
            "coverage_p1": 0.8,
            "coverage_p2": 0.6,
            "forensics": {"p1_name": "Alpha", "p2_name": "Beta"},
            "news_adjustment": {"applied": True},
        },
        {
            "match": "[14:00] Gamma vs Delta",
            "commence_time": "2026-06-17T14:00:00",
            "surface": "Clay",
            "edge": 0.21,
            "value_side": 2,
            "low_confidence": True,
            "confidence_flag": "LOW_COVERAGE",
            "coverage_p1": 0.2,
            "coverage_p2": 0.4,
            "forensics": {"p1_name": "Gamma", "p2_name": "Delta"},
            "news_adjustment": {"applied": False},
        },
        {
            "match": "[16:00] Epsilon vs Zeta",
            "surface": "Grass",
            "edge": -0.03,
            "value_side": 1,
            "low_confidence": False,
            "coverage_p1": 1.0,
            "coverage_p2": 1.0,
            "forensics": {"p1_name": "Epsilon", "p2_name": "Zeta"},
            "news_adjustment": None,
        },
    ]

    summary = build_scan_summary(
        predictions,
        generated_at=datetime(2026, 6, 16, 10, 30, tzinfo=timezone.utc),
        top_n=2,
    )

    assert summary["generated_at"] == "2026-06-16T10:30:00Z"
    assert summary["match_count"] == 3
    assert summary["positive_edge_count"] == 2
    assert summary["low_confidence_count"] == 1
    assert summary["news_adjusted_count"] == 1
    assert summary["average_coverage"] == pytest.approx(0.667)
    assert summary["surface_counts"] == {"Clay": 1, "Grass": 2}
    assert summary["confidence_flags"] == {"LOW_COVERAGE": 1}
    assert [item["match"] for item in summary["top_edges"]] == [
        "[14:00] Gamma vs Delta",
        "[12:00] Alpha vs Beta",
    ]
    assert summary["top_edges"][0]["value_player"] == "Delta"


def test_build_scan_summary_handles_empty_predictions():
    summary = build_scan_summary(
        [],
        generated_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )

    assert summary["match_count"] == 0
    assert summary["average_coverage"] == 0.0
    assert summary["surface_counts"] == {}
    assert summary["confidence_flags"] == {}
    assert summary["top_edges"] == []


@pytest.mark.slow
def test_load_resources_returns_expected_tuple_shape():
    """load_resources() must return a 7-tuple with expected types."""
    from src.live.inference import load_resources

    # Try to load resources; skip if model artifacts aren't present
    try:
        result = load_resources()
    except FileNotFoundError as e:
        pytest.skip(f"Model artifacts not found: {e}")
    except Exception as e:
        # Other errors (e.g., pickle version mismatch) are real failures
        raise

    # Must be a 7-tuple:
    # (config, elo_engine, stats_engine, models_dict, scaler, feature_cols, medians)
    assert isinstance(result, tuple), "load_resources() must return a tuple"
    assert len(result) == 7, f"Expected 7-tuple, got {len(result)}-tuple"

    config, elo_engine, stats_engine, models_dict, scaler, feature_cols, medians = result

    # config: dict with expected keys
    assert isinstance(config, dict), "config must be a dict"
    assert "model" in config, "config missing 'model' section"
    assert "paths" in config, "config missing 'paths' section"

    # elo_engine: has expected attributes
    assert hasattr(elo_engine, "global_ratings"), "elo_engine missing global_ratings"
    assert hasattr(elo_engine, "get_combined_rating"), "elo_engine missing get_combined_rating"

    # stats_engine: has get_player_features
    assert hasattr(stats_engine, "get_player_features"), "stats_engine missing get_player_features"

    # models_dict: dict with h2h, spread, totals
    assert isinstance(models_dict, dict), "models_dict must be a dict"
    assert "h2h" in models_dict, "models_dict missing 'h2h' model"
    assert "spread" in models_dict, "models_dict missing 'spread' model"
    assert "totals" in models_dict, "models_dict missing 'totals' model"

    # scaler: has transform method and feature_names_in_
    assert hasattr(scaler, "transform"), "scaler missing transform method"
    assert hasattr(scaler, "feature_names_in_"), "scaler missing feature_names_in_"

    # feature_cols: list of strings
    assert isinstance(feature_cols, list), "feature_cols must be a list"
    assert all(isinstance(c, str) for c in feature_cols), "feature_cols must contain strings"
    assert len(feature_cols) > 0, "feature_cols must not be empty"

    # medians: dict
    assert isinstance(medians, dict), "medians must be a dict"


def test_agentic_research_recalculates_roi_edge(monkeypatch):
    """Agentic adjustments must keep the same edge semantics as live inference."""
    from src.live import agentic_research

    class FakeAgent:
        def research_matches(self, predictions):
            return [{
                "match": "[12:00] Alpha vs Beta",
                "adjustment": 0.05,
                "confidence": 1.0,
                "reason": "fitness",
            }]

    monkeypatch.setattr(agentic_research, "AgenticResearcher", FakeAgent)

    predictions = [{
        "match": "[12:00] Alpha vs Beta",
        "prob_1": 0.84,
        "prob_2": 0.16,
        "odds_1": 1.01,
        "odds_2": 7.70,
    }]

    result = agentic_research.run_agentic_research(predictions)

    assert result[0]["prob_1"] == pytest.approx(0.89)
    assert result[0]["edge"] == pytest.approx((1.01 * 0.89) - 1)
    assert result[0]["value_side"] == 1
    assert result[0]["news_adjustment"]["applied"] is True
