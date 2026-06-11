"""
Sanity invariants for the ELO rating system.
"""
import pandas as pd
import pytest

from src.features.elo import EloRating, parse_score_games


def test_expected_score_equal_ratings():
    elo = EloRating()
    assert elo.expected_score(1500, 1500) == pytest.approx(0.5)


def test_expected_score_symmetric():
    elo = EloRating()
    a, b = 1600, 1450
    assert elo.expected_score(a, b) + elo.expected_score(b, a) == pytest.approx(1.0)


def test_expected_score_monotonic_and_400_gap():
    elo = EloRating()
    assert elo.expected_score(1700, 1500) > elo.expected_score(1600, 1500) > 0.5
    # A 400-point edge is the canonical ~10:1 (0.909) favourite.
    assert elo.expected_score(1900, 1500) == pytest.approx(0.909, abs=1e-3)


def test_update_winner_gains_loser_loses():
    elo = EloRating()
    elo.update(winner_id="A", loser_id="B", surface="Hard")
    assert elo.global_ratings["A"] > 1500
    assert elo.global_ratings["B"] < 1500


def test_update_is_zero_sum_for_equal_players():
    """Equal base K (same level, both newcomers) -> winner gain == loser loss."""
    elo = EloRating()
    elo.update(winner_id="A", loser_id="B", surface="Hard")
    gain = elo.global_ratings["A"] - 1500
    loss = 1500 - elo.global_ratings["B"]
    assert gain == pytest.approx(loss)


def test_match_counts_increment():
    elo = EloRating()
    elo.update(winner_id="A", loser_id="B", surface="Clay")
    assert elo.match_count["A"] == 1
    assert elo.match_count["B"] == 1


def test_newcomer_k_factor_higher():
    elo = EloRating()
    elo.match_count["veteran"] = 50
    veteran_k = elo._get_k_factor("A", "veteran")
    newcomer_k = elo._get_k_factor("A", "rookie")  # 0 matches -> boosted
    assert newcomer_k > veteran_k
    assert veteran_k == elo.k_factor  # 50 matches -> base level-A K (32)


def test_time_decay_pulls_toward_mean():
    elo = EloRating()
    elo.global_ratings["A"] = 1800
    elo.last_played_date["A"] = pd.Timestamp("2024-01-01")
    elo.apply_time_decay("A", pd.Timestamp("2025-01-01"))  # ~365 days inactive
    # Decays toward 1500 but not past it.
    assert 1500 < elo.global_ratings["A"] < 1800


def test_time_decay_noop_when_recent():
    elo = EloRating()
    elo.global_ratings["A"] = 1800
    elo.last_played_date["A"] = pd.Timestamp("2024-01-01")
    elo.apply_time_decay("A", pd.Timestamp("2024-01-15"))  # <30 days
    assert elo.global_ratings["A"] == 1800


@pytest.mark.parametrize("score,expected", [
    ("6-4 6-3", (12, 7)),
    ("6-4 3-6 7-5", (16, 15)),
    ("7-6(5) 6-4", (13, 10)),   # tiebreak points stripped
    ("6-0 W/O", (0, 0)),         # walkover -> no games
])
def test_parse_score_games(score, expected):
    assert parse_score_games(score) == expected
