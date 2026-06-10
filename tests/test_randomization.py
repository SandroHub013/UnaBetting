"""
Invariants for `_randomize_perspective` (perspective-swap augmentation).

Flipping player 1 <-> player 2 must preserve symmetric quantities and atomically
flip the asymmetric ones, or the model trains on inconsistent rows.
"""
import numpy as np
import pandas as pd

from src.models.train import _randomize_perspective


def _frame(n=200):
    rng = np.random.RandomState(7)
    X = pd.DataFrame({
        "w_ace": rng.randint(0, 30, n).astype(float),
        "l_ace": rng.randint(0, 30, n).astype(float),
        "diff_rank": rng.normal(size=n),
        "rank_diff": rng.normal(size=n),
        "elo_win_prob": rng.uniform(0.05, 0.95, n),
        "B365W": rng.uniform(1.1, 5.0, n),
        "B365L": rng.uniform(1.1, 5.0, n),
        "neutral_feat": rng.normal(size=n),
    })
    y = pd.DataFrame({
        "target": rng.randint(0, 2, n),
        "game_diff": rng.randint(-6, 6, n).astype(float),
        "total_games": rng.randint(12, 39, n).astype(float),
    })
    return X, y


def test_total_games_invariant():
    """total_games is symmetric (p1+p2) — must be unchanged by the swap."""
    X, y = _frame()
    _, y_r = _randomize_perspective(X, y)
    pd.testing.assert_series_equal(y["total_games"], y_r["total_games"], check_names=False)


def test_column_set_preserved():
    """Swap must not add, drop, or reorder columns."""
    X, y = _frame()
    X_r, y_r = _randomize_perspective(X, y)
    assert list(X_r.columns) == list(X.columns)
    assert list(y_r.columns) == list(y.columns)


def test_target_flip_matches_elo_prob_flip():
    """Flipped rows: target -> 1-target AND elo_win_prob -> 1-prob, atomically."""
    X, y = _frame()
    X_r, y_r = _randomize_perspective(X, y)

    flipped = ~np.isclose(X_r["elo_win_prob"].to_numpy(), X["elo_win_prob"].to_numpy())
    # On flipped rows, elo prob is complemented and target is inverted.
    assert np.allclose(
        X_r.loc[flipped, "elo_win_prob"], 1.0 - X.loc[flipped, "elo_win_prob"]
    )
    assert (y_r.loc[flipped, "target"] == 1 - y.loc[flipped, "target"]).all()
    # Non-flipped rows untouched.
    assert (y_r.loc[~flipped, "target"] == y.loc[~flipped, "target"]).all()


def test_w_l_columns_swapped_together():
    """w_ace and l_ace must swap as a pair on flipped rows (atomic)."""
    X, y = _frame()
    X_r, _ = _randomize_perspective(X, y)
    flipped = ~np.isclose(X_r["elo_win_prob"].to_numpy(), X["elo_win_prob"].to_numpy())
    assert np.allclose(X_r.loc[flipped, "w_ace"], X.loc[flipped, "l_ace"])
    assert np.allclose(X_r.loc[flipped, "l_ace"], X.loc[flipped, "w_ace"])


def test_deterministic_seed():
    """Same seed -> identical output (model/scaler/medians must stay in sync)."""
    X, y = _frame()
    X_r1, y_r1 = _randomize_perspective(X, y, seed=42)
    X_r2, y_r2 = _randomize_perspective(X, y, seed=42)
    pd.testing.assert_frame_equal(X_r1, X_r2)
    pd.testing.assert_frame_equal(y_r1, y_r2)
