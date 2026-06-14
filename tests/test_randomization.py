"""Perspective randomization must flip both features and labels."""
import pandas as pd

from src.models.train import _randomize_perspective


def test_randomize_perspective_swaps_features_and_targets():
    X = pd.DataFrame({
        "w_serve": [0.60, 0.70, 0.65, 0.80],
        "l_serve": [0.40, 0.30, 0.35, 0.20],
        "B365W": [1.90, 1.80, 1.75, 1.70],
        "B365L": [2.10, 2.20, 2.25, 2.30],
        "diff_elo": [100, 120, 80, 150],
        "rank_ratio": [2.0, 1.5, 3.0, 1.25],
        "elo_win_prob": [0.60, 0.70, 0.55, 0.80],
    })
    y = pd.DataFrame({
        "target": [1, 0, 1, 0],
        "game_diff": [2, -3, 1, -4],
        "total_games": [20, 22, 19, 24],
    })
    flip_mask = pd.Series([False, True, False, True])

    X_r, y_r = _randomize_perspective(X, y, flip_mask=flip_mask)

    expected_X = pd.DataFrame({
        "w_serve": [0.60, 0.30, 0.65, 0.20],
        "l_serve": [0.40, 0.70, 0.35, 0.80],
        "B365W": [1.90, 2.20, 1.75, 2.30],
        "B365L": [2.10, 1.80, 2.25, 1.70],
        "diff_elo": [100, -120, 80, -150],
        "rank_ratio": [2.0, 1 / 1.5, 3.0, 1 / 1.25],
        "elo_win_prob": [0.60, 0.30, 0.55, 0.20],
    })
    expected_y = pd.DataFrame({
        "target": [1, 1, 1, 1],
        "game_diff": [2, 3, 1, 4],
        "total_games": [20, 22, 19, 24],
    })

    pd.testing.assert_frame_equal(X_r, expected_X, check_exact=False, atol=1e-12)
    pd.testing.assert_frame_equal(y_r, expected_y, check_exact=False, atol=1e-12)
