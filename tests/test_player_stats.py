"""
Feature-correctness tests for PlayerStatsEngine.
"""
import numpy as np
import pandas as pd
import pytest

from src.features.player_stats import PlayerStatsEngine


def test_avg_games_per_set_pairs_per_match():
    """
    games-per-set must pair each match's own games with its own sets.

    The old code zipped two independently filtered lists. Here matches 3 and 4
    are each missing one field, so independent filtering produced lists of
    games=[24,39,20] and sets=[2,3,2] — equal length but mis-paired (20 games
    wrongly divided by 2 sets from a different match -> mean 11.67).
    Correct per-match pairing uses only matches 1 and 2 -> mean (12+13)/2 = 12.5.
    """
    eng = PlayerStatsEngine()
    matches = [
        {"total_games": 24, "n_sets": 2},        # 12.0
        {"total_games": 39, "n_sets": 3},        # 13.0
        {"total_games": 20, "n_sets": None},     # excluded: no n_sets
        {"total_games": None, "n_sets": 2},      # excluded: no games
    ]
    stats = eng._totals_stats(matches)
    assert stats["avg_games_per_set"] == 12.5


def test_avg_games_per_set_not_nan_on_length_mismatch():
    """A length mismatch between available games/sets must not NaN the feature."""
    eng = PlayerStatsEngine()
    matches = [
        {"total_games": 26, "n_sets": 2},        # 13.0
        {"total_games": 18, "n_sets": None},     # excluded
    ]
    stats = eng._totals_stats(matches)
    assert not np.isnan(stats["avg_games_per_set"])
    assert stats["avg_games_per_set"] == 13.0


def test_avg_games_per_set_nan_when_no_valid_match():
    """No usable match -> NaN (genuine missing, not silent error)."""
    eng = PlayerStatsEngine()
    stats = eng._totals_stats([{"total_games": None, "n_sets": None}])
    assert np.isnan(stats["avg_games_per_set"])


# --- momentum / form features ---

def test_form_all_wins():
    eng = PlayerStatsEngine()
    matches = [{"won": True} for _ in range(6)]
    f = eng._form_features(matches)
    assert f["form_ewm"] == pytest.approx(1.0)
    assert f["recent_form_5"] == pytest.approx(1.0)
    assert f["current_streak"] == 6.0  # six consecutive wins


def test_form_streak_signed_negative_on_loss():
    eng = PlayerStatsEngine()
    matches = [{"won": True}, {"won": True}, {"won": False}]
    f = eng._form_features(matches)
    assert f["current_streak"] == -1.0  # last result is a single loss


def test_form_ewm_weights_recent_more():
    """A recent win should lift form above the flat mean given an early loss."""
    eng = PlayerStatsEngine()
    matches = [{"won": False}, {"won": True}]  # flat mean 0.5, recent=win
    f = eng._form_features(matches)
    assert f["form_ewm"] > 0.5


def test_form_empty():
    eng = PlayerStatsEngine()
    f = eng._form_features([])
    assert np.isnan(f["form_ewm"])
    assert f["current_streak"] == 0.0


# --- recency-weighted H2H ---

def test_h2h_recent_win_rate_windowed():
    eng = PlayerStatsEngine()
    old = pd.Timestamp("2020-01-01")
    recent = pd.Timestamp("2026-01-01")
    # A beat B long ago, B beat A recently (twice).
    eng.h2h_history[("A", "B")] = [(old, 1.0), (recent, 0.0), (recent, 0.0)]
    feats = eng.get_player_features("A", "Hard", opponent_id="B",
                                    match_date=pd.Timestamp("2026-02-01"))
    # Only the two recent meetings (<=730d) count -> A lost both -> 0.0
    assert feats["h2h_recent_win_rate"] == pytest.approx(0.0)
    assert feats["h2h_recent_n"] == 2.0


def test_fatigue_accumulates_load():
    eng = PlayerStatsEngine()
    now = pd.Timestamp("2026-05-01")
    matches = [
        {"date": pd.Timestamp("2026-04-25"), "total_games": 30, "minutes": 120, "n_sets": 3, "won": True},
        {"date": pd.Timestamp("2026-04-28"), "total_games": 20, "minutes": 90, "n_sets": 2, "won": True},
    ]
    f = eng._fatigue_features(matches, now)
    assert f["matches_last_14d"] == 2
    assert f["games_last_14d"] == 50
    assert f["minutes_last_14d"] == 210
