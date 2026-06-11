"""
Regression guard against target/look-ahead leakage in the training pipeline.

The historical bug: `prepare_training_data` imputed NaNs with the median of the
ENTIRE dataset (train+val+test) BEFORE the temporal split, leaking the future
distribution into the training set and inflating reported accuracy/ROI.

These tests pin the invariant: imputation medians must be computed TRAIN-ONLY.
"""
import numpy as np
import pandas as pd
import pytest

from src.models.train import (
    prepare_training_data, load_config, _randomize_perspective,
    _enforce_perspective_pairs, _assert_no_unpaired_perspective, _perspective_partner,
)


def _synthetic_features():
    """
    Build a tiny features frame where the train-only median and the
    global (train+val) median DIVERGE for `feat_x`:

      train (2018-2019): feat_x = [1, 2, 3, 4]   -> median 2.5
      val   (2020):      feat_x = [100, 100]      -> shifts global median to 3.5
      test  (2021):      feat_x = NaN             -> must be imputed with TRAIN median

    `feat_x` is named so `_randomize_perspective` never touches it (no w_/l_/diff_
    prefix, no W/L suffix), so its values are stable through the pipeline.
    """
    rows = []
    # train rows
    for yr, fx in [(2018, 1.0), (2018, 2.0), (2019, 3.0), (2019, 4.0)]:
        rows.append({"tourney_date": f"{yr}-06-01", "feat_x": fx})
    # validation rows (large values -> pull the global median up)
    for _ in range(2):
        rows.append({"tourney_date": "2020-06-01", "feat_x": 100.0})
    # test rows (feat_x missing -> imputed)
    for _ in range(3):
        rows.append({"tourney_date": "2021-06-01", "feat_x": np.nan})

    df = pd.DataFrame(rows)
    # required target columns (non-NaN so rows survive the dropna)
    n = len(df)
    rng = np.random.RandomState(0)
    df["target"] = rng.randint(0, 2, n)
    df["game_diff"] = rng.randint(-6, 6, n)
    df["total_games"] = rng.randint(12, 39, n)
    # a second stable numeric feature so the frame has >1 column
    df["feat_y"] = rng.normal(size=n)
    df["winner_id"] = ["A"] * n
    df["loser_id"] = ["B"] * n
    return df


def _config():
    cfg = load_config()
    cfg["model"]["test_start_year"] = 2021
    cfg["model"]["validation_years"] = [2020]
    return cfg


def test_imputation_median_is_train_only():
    """The saved medians must reflect ONLY the train window, not val/test."""
    df = _synthetic_features()
    cfg = _config()

    res = prepare_training_data(df, cfg, skip_selection=True)
    medians = res[-2]

    # Train feat_x = [1,2,3,4] -> 2.5.  Global (incl. val 100s) would be 3.5.
    assert "feat_x" in medians
    assert medians["feat_x"] == pytest.approx(2.5), (
        f"feat_x median is {medians['feat_x']}, expected train-only 2.5. "
        "A value near 3.5 means val/test leaked into imputation."
    )


def test_no_nan_after_imputation():
    """Every split must be fully imputed (no NaN reaches the model/scaler)."""
    df = _synthetic_features()
    cfg = _config()

    X_train, _, X_val, _, X_test, *_ = prepare_training_data(df, cfg, skip_selection=True)

    for name, X in [("train", X_train), ("val", X_val), ("test", X_test)]:
        assert not X.isna().any().any(), f"NaN present in {name} after imputation"


def test_perspective_pairs_added_when_partner_available():
    """An unpaired w_X must get its l_X partner pulled in when available."""
    cols = _enforce_perspective_pairs(
        ["w_serve", "elo_win_prob", "diff_x"],
        available_cols=["w_serve", "l_serve", "elo_win_prob", "diff_x"],
    )
    assert "l_serve" in cols  # partner added
    assert "diff_x" in cols and "elo_win_prob" in cols  # self-symmetric kept


def test_perspective_pairs_drop_when_partner_missing():
    """If the partner does not exist in the data, the leaky column is dropped."""
    cols = _enforce_perspective_pairs(
        ["w_serve", "elo_win_prob"], available_cols=["w_serve", "elo_win_prob"],
    )
    assert "w_serve" not in cols  # cannot pair -> dropped (leak risk)


def test_odds_suffix_partner_detected():
    assert _perspective_partner("B365W") == "B365L"
    assert _perspective_partner("MaxL") == "MaxW"
    assert _perspective_partner("diff_x") is None  # self-symmetric


def test_randomize_raises_on_unpaired_perspective():
    """_randomize_perspective must refuse to run on unpaired perspective cols."""
    X = pd.DataFrame({"w_serve": [0.6, 0.7], "elo_win_prob": [0.5, 0.5]})
    y = pd.DataFrame({"target": [1, 0], "game_diff": [1, -1], "total_games": [20, 22]})
    with pytest.raises(ValueError, match="[Uu]npaired"):
        _randomize_perspective(X, y)


@pytest.mark.slow
def test_serve_only_walkforward_roc_is_not_leaky():
    """Names the unpaired-column leak: serve rolling stats alone must NOT
    reconstruct the outcome. Pre-fix this hit ROC ~0.96 (flip reconstruction via
    unpaired w_ columns); leak-free it should sit near market level (< 0.82).
    Walk-forward: train on all years < 2024, test on 2024 (full serve data).
    """
    import copy
    from pathlib import Path
    import xgboost as xgb
    from sklearn.metrics import roc_auc_score

    cfg = load_config()
    root = Path(__file__).resolve().parent.parent
    features_path = root / cfg["paths"]["features"] / "atp_features.csv"
    if not features_path.exists():
        pytest.skip(f"features not built: {features_path}")

    df = pd.read_csv(features_path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
    cfg = copy.deepcopy(cfg)
    cfg["model"]["test_start_year"] = 2024
    cfg["model"]["validation_years"] = []
    Xtr, ytr, _, _, Xte, yte, *_ = prepare_training_data(df, cfg)

    yor = df["tourney_date"].dt.year
    mk = Xte.index.map(yor) == 2024
    serve_pats = ["pct_2nd_won", "pct_1st_won", "pct_1st_in", "ace_rate",
                  "df_rate", "bp_save", "hold_pct"]
    serve = [c for c in Xtr.columns
             if c.startswith(("w_", "l_")) and any(p in c for p in serve_pats)
             and "clutch" not in c]
    if len(serve) < 4:
        pytest.skip("serve features not present in selection")

    m = xgb.XGBClassifier(**cfg["model"]["xgboost"], random_state=42, eval_metric="logloss")
    m.fit(Xtr[serve], ytr["target"].to_numpy())
    roc = roc_auc_score(yte[mk]["target"].to_numpy(), m.predict_proba(Xte[mk][serve])[:, 1])
    assert roc < 0.82, (
        f"serve-only walk-forward ROC {roc:.3f} >= 0.82 — unpaired-column "
        "perspective leak likely reintroduced."
    )


@pytest.mark.slow
def test_shuffled_target_accuracy_is_chance():
    """
    Classic leakage detector on the REAL dataset: train on shuffled targets and
    assert test accuracy collapses to chance. If the pipeline leaks, a model can
    still 'predict' shuffled labels above chance. Skips if features are absent.
    """
    from pathlib import Path
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score

    cfg = load_config()
    root = Path(__file__).resolve().parent.parent
    features_path = root / cfg["paths"]["features"] / "atp_features.csv"
    if not features_path.exists():
        pytest.skip(f"features not built: {features_path}")

    df = pd.read_csv(features_path, low_memory=False)
    X_train, y_train, _, _, X_test, y_test, *_ = prepare_training_data(df, cfg)
    y_tr = y_train["target"].to_numpy()
    y_te = y_test["target"].to_numpy()

    rng = np.random.RandomState(42)
    y_tr_shuffled = rng.permutation(y_tr)

    model = LogisticRegression(max_iter=500)
    model.fit(X_train, y_tr_shuffled)
    acc = accuracy_score(y_te, model.predict(X_test))

    assert acc < 0.58, (
        f"Shuffled-target test accuracy {acc:.3f} >= 0.58 — pipeline likely leaks."
    )
