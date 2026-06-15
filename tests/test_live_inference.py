"""
Smoke test for the live inference load_resources() function.

This test guards against the class of breakage where model artifacts change
format (legacy bare pickle vs bundle dict) or the return tuple shape changes.
"""
import pytest


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