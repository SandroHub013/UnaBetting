"""
Tennis Prediction Model - Model Training Pipeline
Trains and evaluates multiple ML models for match prediction.
"""

import pandas as pd
import numpy as np
import yaml
import joblib
from pathlib import Path
from datetime import datetime

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, log_loss, brier_score_loss, roc_auc_score
)
from sklearn.calibration import CalibratedClassifierCV

try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    from src.models.pytorch_ensemble import TennisTransformerNet, train_tennis_model
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    Dataset = object  # TennisDataset is only instantiated when HAS_TORCH

class PreFittedEnsemble:
    """Wrapper per evitare il re-training di tutti gli stimatori nell'Ensemble.
    Usa modelli già fittati (e calibrati) e calcola la media ponderata delle loro probabilità."""
    def __init__(self, models, is_regression=False, weights=None):
        self.models = models
        self.is_regression = is_regression
        if weights is None:
            self.weights = np.ones(len(models)) / len(models)
        else:
            self.weights = np.array(weights)

    def predict(self, X):
        if self.is_regression:
            preds = np.column_stack([m.predict(X) for m in self.models])
            return np.average(preds, axis=1, weights=getattr(self, "weights", None))
        else:
            return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X):
        probs = np.array([m.predict_proba(X) for m in self.models])
        return np.average(probs, axis=0, weights=getattr(self, "weights", None))


# Pickle identity across entrypoints. When this file runs as
# `python -m src.models.train` the class lives in __main__; live inference imports
# it as src.models.train. Forcing __module__ alone makes pickle look up
# src.models.train.PreFittedEnsemble and compare identity — which fails ("not the
# same object") if src.models.train is loaded as a SEPARATE module during the run.
# Alias the running module under the canonical name so the class object is
# identical on both save (training) and load (inference).
import sys as _sys
_MODULE_NAME = "src.models.train"
PreFittedEnsemble.__module__ = _MODULE_NAME
_canon = _sys.modules.get(_MODULE_NAME)
if _canon is None:
    _sys.modules[_MODULE_NAME] = _sys.modules[__name__]
elif _canon is not _sys.modules[__name__]:
    _canon.PreFittedEnsemble = PreFittedEnsemble


try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


#: column-name fragments that mark a bookmaker price
_ODDS_TOKENS = ("B365", "PS", "MAX", "AVG")

#: everything that is metadata or a label rather than a feature
_META_COLS = ("tourney_date", "tourney_name", "surface", "tourney_level",
              "winner_name", "loser_name", "winner_id", "loser_id", "score",
              "target", "game_diff", "total_games")


def _select_feature_cols(df, skip_selection, tour):
    """Feature columns, optionally narrowed by the saved selection file."""
    meta_cols = list(_META_COLS)
    meta_cols += [c for c in df.columns
                  if any(bk in c.upper() for bk in _ODDS_TOKENS)]
    feature_cols = [c for c in df.columns if c not in meta_cols]
    if skip_selection:
        return feature_cols

    selection_path = PROJECT_ROOT / "config" / f"selected_features_{tour}.txt"
    if not selection_path.exists():
        selection_path = PROJECT_ROOT / "config" / "selected_features_atp.txt"
    if not selection_path.exists():
        return feature_cols

    with open(selection_path, "r") as f:
        selected = [line.strip() for line in f if line.strip()]
    original_count = len(feature_cols)
    feature_cols = [c for c in feature_cols if c in selected]
    if len(feature_cols) < original_count:
        print(f"  [+] Feature Selection: Ridotte da {original_count} a {len(feature_cols)}")
    return feature_cols


def _temporal_masks(df, test_year, val_years):
    """Train / validation / test row masks, split strictly by season."""
    year_col = df["tourney_date"].dt.year
    test_mask = year_col >= test_year
    if val_years:
        return year_col < min(val_years), year_col.isin(val_years), test_mask
    # no separate validation set
    return year_col < test_year, pd.Series(False, index=df.index), test_mask


def _scale_split(scaler, X, fit=False):
    """Scale one split. An empty validation set is legitimate (walk-forward CV
    passes validation_years=[]) but sklearn's transform rejects 0-row arrays.
    """
    if len(X) == 0:
        return pd.DataFrame(columns=X.columns, index=X.index)
    arr = scaler.fit_transform(X) if fit else scaler.transform(X)
    return pd.DataFrame(arr, columns=X.columns, index=X.index)


def _add_player_ids(df, train_mask):
    """Embed indices for the PyTorch model, fitted on train only (0 is UNK)."""
    p1_raw = np.where(df["target"] == 1, df["winner_id"], df["loser_id"])
    p2_raw = np.where(df["target"] == 1, df["loser_id"], df["winner_id"])
    train_players = np.unique(np.concatenate([p1_raw[train_mask], p2_raw[train_mask]]))
    player_mapping = {pid: i + 1 for i, pid in enumerate(train_players)}
    df["p1_id"] = np.array([player_mapping.get(p, 0) for p in p1_raw])
    df["p2_id"] = np.array([player_mapping.get(p, 0) for p in p2_raw])
    return player_mapping


def prepare_training_data(features_df, config, skip_selection=False, tour="atp"):
    """
    Prepare train / validation / test sets using temporal split.
    - Train: years < validation_years (e.g. < 2023)
    - Validation: validation_years (e.g. 2023-2024) — used for calibration
    - Test: years >= test_start_year (e.g. >= 2025)
    Critical: NEVER use random split for time-series sports data!
    """
    df = features_df.copy()

    # Parse dates
    if "tourney_date" in df.columns:
        df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
        df = df.dropna(subset=["tourney_date"])

    # Drop rows with NaN targets (critical for regression)
    df = df.dropna(subset=["target", "game_diff", "total_games"])

    feature_cols = _select_feature_cols(df, skip_selection, tour)

    # CRITICAL: enforce perspective-pair completeness. A w_X feature whose l_X
    # partner is absent is never swapped by _randomize_perspective, so it keeps
    # winner-POV data → the model reconstructs the 50% flip = the target (severe
    # leak). This guard makes the pipeline robust even to a stale/edited
    # selection file. See _enforce_perspective_pairs.
    feature_cols = _enforce_perspective_pairs(feature_cols, df.columns)

    # Randomize perspective FIRST to mix winners and losers evenly
    print("  [+] Randomizzazione prospettiva...")
    y_cols = ["target", "game_diff", "total_games"]
    df_r, y_r = _randomize_perspective(df[feature_cols], df[y_cols])

    # NOTE: imputation is DEFERRED until after the temporal split below.
    # Computing medians here (over train+val+test combined) leaks the future
    # distribution into the training set — look-ahead bias. Medians are computed
    # train-only post-split (see below) and reused for val/test/live inference.
    df[feature_cols] = df_r
    df[y_cols] = y_r

    # Temporal split: train / validation / test
    test_year = config["model"]["test_start_year"]
    val_years = config["model"].get("validation_years", [])
    val_start = min(val_years) if val_years else None
    train_mask, val_mask, test_mask = _temporal_masks(df, test_year, val_years)

    x_train = df.loc[train_mask, feature_cols].copy()
    y_train = df.loc[train_mask, y_cols].copy()
    x_val = df.loc[val_mask, feature_cols].copy()
    y_val = df.loc[val_mask, y_cols].copy()
    x_test = df.loc[test_mask, feature_cols].copy()
    y_test = df.loc[test_mask, y_cols].copy()

    # Remove any non-numeric columns that slipped through
    numeric_cols = x_train.select_dtypes(include=[np.number]).columns.tolist()
    x_train = x_train[numeric_cols]
    x_val = x_val[numeric_cols]
    x_test = x_test[numeric_cols]

    # Impute missing values using TRAIN-ONLY medians (no look-ahead leakage).
    # Computed BEFORE fillna so the saved medians reflect true train distribution.
    # fillna(0.0) guards features that are all-NaN within the train window.
    medians_series = x_train.median().fillna(0.0)
    x_train = x_train.fillna(medians_series)
    x_val = x_val.fillna(medians_series)
    x_test = x_test.fillna(medians_series)

    scaler = StandardScaler()
    x_train_scaled = _scale_split(scaler, x_train, fit=True)
    x_val_scaled = _scale_split(scaler, x_val)
    x_test_scaled = _scale_split(scaler, x_test)

    player_mapping = _add_player_ids(df, train_mask)
    p_train = df.loc[train_mask, ["p1_id", "p2_id"]].copy()
    p_val = df.loc[val_mask, ["p1_id", "p2_id"]].copy()
    p_test = df.loc[test_mask, ["p1_id", "p2_id"]].copy()

    val_start_str = f"{min(val_years)}-{max(val_years)}" if val_years else "N/A"
    print(f"  [+] Training: {len(x_train):,} partite (prima del {val_start if val_years else test_year})")
    print(f"  [+] Validation: {len(x_val):,} partite ({val_start_str}) -- per calibrazione")
    print(f"  [+] Test: {len(x_test):,} partite (dal {test_year})")
    print(f"  [+] Features: {len(numeric_cols)} colonne")
    print(f"  [+] Giocatori univoci: {len(player_mapping)}")
    if len(x_test) < 200:
        print(f"  [!] WARNING: Test set molto piccolo ({len(x_test)} match). Considera di abbassare test_start_year.")

    # Train-only medians for live imputation alignment (computed pre-fillna above)
    medians = medians_series.to_dict()

    return x_train_scaled, p_train, y_train, x_val_scaled, p_val, y_val, x_test_scaled, p_test, y_test, scaler, numeric_cols, medians, player_mapping


def _perspective_partner(col):
    """Return the opposite-perspective column name, or None if self-symmetric.

    Covers w_/l_ prefix (player features) and trailing W/L suffix (bookmaker odds
    like B365W/B365L, MaxW/MaxL). diff_/rank_diff/elo_win_prob etc. are
    self-symmetric (handled by negation/complement in the swap) and return None.
    """
    if col.startswith("w_"):
        return "l_" + col[2:]
    if col.startswith("l_"):
        return "w_" + col[2:]
    if col.endswith("W") and not col.startswith(("w_", "l_", "diff_")):
        return col[:-1] + "L"
    if col.endswith("L") and not col.startswith(("w_", "l_", "diff_")):
        return col[:-1] + "W"
    return None


def _enforce_perspective_pairs(feature_cols, available_cols):
    """Guarantee every perspective-asymmetric feature has its partner present.

    An unpaired w_X / *W column is never swapped during randomization, so it
    leaks the winner perspective (= the target). For each such column we add the
    missing partner if it exists in the data; otherwise we drop the column (it
    cannot be made symmetric). Order is preserved.
    """
    available = set(available_cols)
    selected = set(feature_cols)
    out, added, dropped = [], [], []
    for c in feature_cols:
        partner = _perspective_partner(c)
        if partner is None:
            out.append(c)
        elif partner in selected:
            out.append(c)
        elif partner in available:
            out.append(c)
            out.append(partner)
            added.append(partner)
        else:
            dropped.append(c)
    out = list(dict.fromkeys(out))
    if added:
        print(f"  [pairs] +{len(added)} partner aggiunti per simmetria randomizzazione")
    if dropped:
        print(f"  [pairs] -{len(dropped)} feature spaiate rimosse (rischio leak): {sorted(dropped)}")
    return out


def _assert_no_unpaired_perspective(columns):
    """Defense in depth: any unpaired perspective column reaching randomization
    is a leak bug. Raise loudly rather than train a contaminated model."""
    cols = set(columns)
    unpaired = [c for c in columns
                if (p := _perspective_partner(c)) is not None and p not in cols]
    if unpaired:
        raise ValueError(
            "Unpaired perspective columns would leak the target through "
            f"randomization: {sorted(unpaired)}. Run features through "
            "_enforce_perspective_pairs first."
        )


#: scalar comparisons that invert when the two players swap places
_SIGNED_DIFF_COLS = ("rank_diff", "age_diff", "height_diff")
#: probabilities that become their complement
_PROB_COLS = ("elo_win_prob", "elo_surface_win_prob")


def _swap_perspective_pairs(x_flipped, X, flip_mask):
    """Exchange every w_X with its l_X partner on the flipped rows."""
    for wc in [c for c in X.columns if c.startswith("w_")]:
        lc = "l_" + wc[2:]
        if lc in X.columns:
            # atomic swap via .values so pandas cannot re-align the two columns
            x_flipped.loc[flip_mask, [wc, lc]] = X.loc[flip_mask, [lc, wc]].values


def _negate_differentials(x_flipped, X, flip_mask):
    """diff_ features and the signed comparisons change sign; a ratio inverts."""
    for dc in [c for c in X.columns if c.startswith("diff_")]:
        x_flipped.loc[flip_mask, dc] = -X.loc[flip_mask, dc]
    for col in _SIGNED_DIFF_COLS:
        if col in X.columns:
            x_flipped.loc[flip_mask, col] = -X.loc[flip_mask, col]
    if "rank_ratio" in X.columns:
        x_flipped.loc[flip_mask, "rank_ratio"] = 1.0 / X.loc[flip_mask, "rank_ratio"]


def _swap_odds_columns(x_flipped, X, flip_mask):
    """B365W <-> B365L, MaxW <-> MaxL, ... skipping the w_/l_ families above."""
    all_cols = list(X.columns)
    for cw in all_cols:
        if not cw.endswith("W") or cw.startswith(("w_", "l_", "diff_")):
            continue
        cl = cw[:-1] + "L"
        if cl in all_cols:
            x_flipped.loc[flip_mask, [cw, cl]] = X.loc[flip_mask, [cl, cw]].values


def _complement_probabilities(x_flipped, X, flip_mask):
    for col in _PROB_COLS:
        if col in X.columns:
            x_flipped.loc[flip_mask, col] = 1.0 - X.loc[flip_mask, col]


def _flip_targets(y, flip_mask):
    """target inverts, game_diff changes sign, total_games is invariant."""
    y_flipped = y.copy()
    if hasattr(y, 'columns'):
        if "target" in y.columns:
            y_flipped.loc[flip_mask, "target"] = 1 - y.loc[flip_mask, "target"]
        if "game_diff" in y.columns:
            y_flipped.loc[flip_mask, "game_diff"] = -y.loc[flip_mask, "game_diff"]
    elif y.name == "target":
        y_flipped.loc[flip_mask] = 1 - y_flipped.loc[flip_mask]
    return y_flipped


def _randomize_perspective(X, y, seed=42, flip_mask=None):
    """
    Randomly swap player 1 and player 2 to avoid the model learning
    that player 1 always wins. Flips ~50% of rows.
    Uses a fixed seed for reproducibility — model, scaler, and medians
    must all come from the same randomization.
    Pass an explicit boolean ``flip_mask`` to flip specific rows (e.g. all rows for
    an orientation-invariant inference); otherwise the mask is drawn from ``seed``.
    """
    _assert_no_unpaired_perspective(X.columns)

    n = len(X)
    if flip_mask is None:
        rng = np.random.default_rng(seed)
        flip_mask = rng.random(n) > 0.5

    x_flipped = X.copy()
    _swap_perspective_pairs(x_flipped, X, flip_mask)
    _negate_differentials(x_flipped, X, flip_mask)
    _swap_odds_columns(x_flipped, X, flip_mask)
    _complement_probabilities(x_flipped, X, flip_mask)
    y_flipped = _flip_targets(y, flip_mask)
    return x_flipped, y_flipped


def _calibrate_classifier(model, x_val, y_val, name, method="isotonic"):
    """Wrap a trained classifier with calibration using the validation set."""
    try:
        calibrated = CalibratedClassifierCV(model, method=method, cv="prefit")
        calibrated.fit(x_val, y_val)
        print(f"    [CAL] {name}: calibrazione {method} applicata su {len(x_val)} match")
        return calibrated
    except Exception as e:
        print(f"    [CAL] {name}: calibrazione fallita ({e}), uso modello originale")
        return model


class TennisDataset(Dataset):
    def __init__(self, p1_ids, p2_ids, features, labels):
        self.p1_ids = torch.tensor(p1_ids.values, dtype=torch.long)
        self.p2_ids = torch.tensor(p2_ids.values, dtype=torch.long)
        self.features = torch.tensor(features.values, dtype=torch.float32)
        self.labels = torch.tensor(labels.values, dtype=torch.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            'p1_id': self.p1_ids[idx],
            'p2_id': self.p2_ids[idx],
            'numerical_features': self.features[idx],
            'label': self.labels[idx]
        }


class _SegmentTrainer:
    """Fit, calibrate and score every model family for one (target, segment)."""

    def __init__(self, target_col, segment, config, is_regression,
                 splits, player_mapping):
        self.target_col = target_col
        self.segment = segment
        self.config = config
        self.is_regression = is_regression
        (self.x_train, self.y_train, self.p_train,
         self.x_val, self.y_val, self.p_val,
         self.x_test, self.y_test, self.p_test) = splits
        self.player_mapping = player_mapping
        self.has_val = len(self.x_val) > 0
        self.has_train = len(self.x_train) > 0
        self.has_test = len(self.x_test) > 0
        self.models = {}
        self.raw_models = {}  # uncalibrated, for feature importance
        self.results = {}

    def key(self, name):
        return f"{self.target_col}_{self.segment}_{name}"

    def _fit_family(self, name, model, label, calibration="isotonic"):
        """Fit, calibrate against the validation split, and score on test."""
        if not self.has_train:
            return
        model.fit(self.x_train, self.y_train)
        self.raw_models[self.key(name)] = model
        if not self.is_regression and self.has_val:
            model = _calibrate_classifier(model, self.x_val, self.y_val, label,
                                          method=calibration)
        self.models[self.key(name)] = model
        if self.has_test:
            self.results[self.key(name)] = _evaluate_model(
                model, self.x_test, self.y_test,
                f"{label} {self.target_col} {self.segment}", self.is_regression)

    def fit_linear(self):
        if self.is_regression:
            from sklearn.linear_model import Ridge
            print(f"\n  [>] Ridge Regression for {self.target_col} ({self.segment})...")
            model = Ridge(alpha=1.0)
        else:
            model = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
            print(f"\n  [>] Logistic Regression for {self.target_col} ({self.segment})...")
        self._fit_family("lr", model, "LR")

    def fit_forest(self):
        if self.is_regression:
            from sklearn.ensemble import RandomForestRegressor
            print(f"\n  [>] Random Forest Regressor for {self.target_col} ({self.segment})...")
            model = RandomForestRegressor(n_estimators=300, max_depth=10,
                                          min_samples_leaf=20, max_features=1.0,
                                          random_state=42, n_jobs=-1)
        else:
            print(f"\n  [>] Random Forest Classifier for {self.target_col} ({self.segment})...")
            model = RandomForestClassifier(n_estimators=300, max_depth=10,
                                           min_samples_leaf=20, max_features="sqrt",
                                           random_state=42, n_jobs=-1)
        self._fit_family("rf", model, "RF")

    def fit_xgboost(self):
        if not HAS_XGB:
            return
        print(f"\n  [>] XGBoost for {self.target_col} ({self.segment})...")
        params = self.config["model"]["xgboost"]
        model = (xgb.XGBRegressor(**params, random_state=42, objective='reg:absoluteerror')
                 if self.is_regression
                 else xgb.XGBClassifier(**params, random_state=42, eval_metric="logloss"))
        self._fit_family("xgboost", model, "XGB", calibration="sigmoid")

    def fit_lightgbm(self):
        if not HAS_LGB:
            return
        print(f"\n  [>] LightGBM for {self.target_col} ({self.segment})...")
        params = self.config["model"]["lightgbm"]
        model = (lgb.LGBMRegressor(**params, random_state=42, verbose=-1,
                                   objective='regression_l1')
                 if self.is_regression
                 else lgb.LGBMClassifier(**params, random_state=42, verbose=-1))
        self._fit_family("lightgbm", model, "LGB")

    def _softmax_weights(self, estimators):
        """Weight each member by exp(-log loss) on the validation split."""
        if not self.has_val:
            return None
        lls = [log_loss(self.y_val, m.predict_proba(self.x_val)) for m in estimators]
        exp_neg_lls = np.exp(-np.array(lls) - np.max(-np.array(lls)))
        return exp_neg_lls / exp_neg_lls.sum()

    def build_ensemble(self):
        if not (self.has_train and self.has_test):
            return
        if self.is_regression:
            print(f"\n  [>] Ensemble (Averaging) for {self.target_col} ({self.segment})...")
            estimators = [self.models[self.key("rf")]]
        else:
            print(f"\n  [>] Ensemble (Softmax -LL Voting) for {self.target_col} ({self.segment})...")
            estimators = [self.models[self.key("lr")], self.models[self.key("rf")]]
        if HAS_XGB:
            estimators.append(self.models[self.key("xgboost")])
        if HAS_LGB:
            estimators.append(self.models[self.key("lightgbm")])

        if self.is_regression:
            ensemble = PreFittedEnsemble(estimators, is_regression=True)
        else:
            ensemble = PreFittedEnsemble(estimators, is_regression=False,
                                         weights=self._softmax_weights(estimators))
        self.models[self.key("ensemble")] = ensemble
        self.results[self.key("ensemble")] = _evaluate_model(
            ensemble, self.x_test, self.y_test,
            f"Ensemble {self.target_col} {self.segment}", self.is_regression)

    def _torch_probabilities(self, nn_model, device):
        test_dataset = TennisDataset(self.p_test['p1_id'], self.p_test['p2_id'],
                                     self.x_test, self.y_test)
        test_loader = DataLoader(test_dataset, batch_size=256, shuffle=False,
                                 num_workers=0)
        probs = []
        with torch.no_grad():
            for batch in test_loader:
                outputs = nn_model(batch['p1_id'].to(device),
                                   batch['p2_id'].to(device),
                                   batch['numerical_features'].to(device))
                probs.extend(outputs.cpu().numpy().flatten())
        return np.array(probs)

    def _score_probabilities(self, y_true, y_prob, tag):
        y_pred = (y_prob >= 0.5).astype(int)
        metrics = {
            "accuracy": accuracy_score(y_true, y_pred),
            "log_loss": log_loss(y_true, y_prob),
            "brier": brier_score_loss(y_true, y_prob),
            "roc_auc": roc_auc_score(y_true, y_prob),
            "ece": _expected_calibration_error(y_true, y_prob),
        }
        print(f"    [{tag}] Accuracy: {metrics['accuracy']:.4f} | "
              f"Log Loss: {metrics['log_loss']:.4f} | "
              f"ROC AUC: {metrics['roc_auc']:.4f} | ECE: {metrics['ece']:.4f}")
        return metrics

    def fit_torch(self):
        """Embedding net over player ids; classification only."""
        if self.is_regression or not self.has_train:
            return
        if not HAS_TORCH:
            print(f"\n  [!] torch not installed — skipping PyTorch Embedding Net "
                  f"for {self.target_col} ({self.segment})")
            return

        print(f"\n  [>] PyTorch Embedding Net for {self.target_col} ({self.segment})...")
        train_loader = DataLoader(
            TennisDataset(self.p_train['p1_id'], self.p_train['p2_id'],
                          self.x_train, self.y_train),
            batch_size=256, shuffle=True, num_workers=0)
        val_loader = DataLoader(
            TennisDataset(self.p_val['p1_id'], self.p_val['p2_id'],
                          self.x_val, self.y_val),
            batch_size=256, shuffle=False, num_workers=0)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        nn_model = TennisTransformerNet(len(self.player_mapping) + 1, 32,
                                        self.x_train.shape[1]).to(device)
        nn_model = train_tennis_model(nn_model, train_loader, val_loader,
                                      epochs=10, lr=0.001)
        self.models[self.key("pytorch")] = nn_model
        if not self.has_test:
            return

        nn_model.eval()
        y_true = self.y_test.values
        y_prob_pt = self._torch_probabilities(nn_model, device)
        self.results[self.key("pytorch")] = self._score_probabilities(
            y_true, y_prob_pt, "PT")

        if HAS_XGB:
            y_prob_xgb = self.models[self.key("xgboost")].predict_proba(self.x_test)[:, 1]
            self.results[self.key("deep_ensemble")] = self._score_probabilities(
                y_true, (y_prob_pt + y_prob_xgb) / 2.0, "DEEP")

    def run(self):
        print(f"\n2. Training modelli {self.segment.upper()} per {self.target_col}...")
        self.fit_linear()
        self.fit_forest()
        self.fit_xgboost()
        self.fit_lightgbm()
        self.build_ensemble()
        self.fit_torch()
        return self.models, self.results


def _train_segment(target_col, segment, config, is_regression, x_train, y_train,
                   p_train, x_val, y_val, p_val, x_test, y_test, p_test,
                   player_mapping):
    splits = (x_train, y_train, p_train, x_val, y_val, p_val,
              x_test, y_test, p_test)
    return _SegmentTrainer(target_col, segment, config, is_regression,
                           splits, player_mapping).run()


class _RoutedPredictions:
    """Test-set predictions stitched back together from the per-segment models."""

    def __init__(self, n_test, is_regression):
        self.is_regression = is_regression
        self.pred = np.zeros(n_test)
        self.prob = None if is_regression else np.zeros(n_test)

    def record(self, model, x_test, mask):
        if model is None or mask.sum() == 0:
            return
        idx = np.nonzero(mask)[0]
        x_segment = x_test[mask]
        self.pred[idx] = model.predict(x_segment)
        if not self.is_regression:
            self.prob[idx] = model.predict_proba(x_segment)[:, 1]

    def score(self, y_test):
        if self.is_regression:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            mae = mean_absolute_error(y_test, self.pred)
            mse = mean_squared_error(y_test, self.pred)
            r2 = r2_score(y_test, self.pred)
            print(f"    Routed MAE: {mae:.4f} | MSE: {mse:.4f} | R2: {r2:.4f}")
            return {"mae": mae, "mse": mse, "r2": r2}

        acc = accuracy_score(y_test, self.pred)
        ll = log_loss(y_test, self.prob)
        brier = brier_score_loss(y_test, self.prob)
        roc = roc_auc_score(y_test, self.prob)
        ece = _expected_calibration_error(np.array(y_test), self.prob)
        print(f"    Routed Accuracy: {acc:.4f} | Log Loss: {ll:.4f} | "
              f"ROC AUC: {roc:.4f} | ECE: {ece:.4f}")
        return {"accuracy": acc, "log_loss": ll, "brier": brier,
                "roc_auc": roc, "ece": ece}


def _save_artifacts(models_dir, tour, all_models, feature_names, player_mapping,
                    scaler, medians):
    """Calibrated models plus everything inference needs to rebuild the input."""
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, model in all_models.items():
        if "pytorch" in name:
            torch.save({"model": model, "feature_cols": list(feature_names),
                        "player_mapping": player_mapping},
                       models_dir / f"{tour}_{name}.pt")
        else:
            joblib.dump({"model": model, "feature_cols": list(feature_names)},
                        models_dir / f"{tour}_{name}.pkl")

    joblib.dump(scaler, models_dir / f"{tour}_scaler.pkl")
    joblib.dump(player_mapping, models_dir / f"{tour}_player_mapping.pkl")
    joblib.dump(medians, models_dir / f"{tour}_medians.pkl")
    # legacy txt for human inspection — the artifact bundle is authoritative
    with open(models_dir / f"{tour}_features.txt", "w") as f:
        f.write("\n".join(feature_names))


def _save_metrics(models_dir, tour, target_col, all_results):
    """Metrics the TUI ticker and the dashboard read."""
    import json as _json

    routed = all_results.get(f"{target_col}_routed_ensemble", {})
    metrics_out = {
        "routed_accuracy": float(routed.get("accuracy", 0)),
        "routed_ece": float(routed.get("ece", 0)),
        "routed_log_loss": float(routed.get("log_loss", 0)),
        "routed_roc_auc": float(routed.get("roc_auc", 0)),
        "all_models": {name: {k: float(v) for k, v in res.items()}
                       for name, res in all_results.items()},
        "trained_at": datetime.now().isoformat(),
    }
    metrics_path = models_dir / f"{tour}_metrics.json"
    with open(metrics_path, "w") as mf:
        _json.dump(metrics_out, mf, indent=2)
    print(f"  [+] Metrics saved to {metrics_path}")


def train_models(tour="atp", target_col="target", save_dir=None, test_year=None, val_years=None):
    """
    Train all configured models for a specific target (target, game_diff, total_games).
    Uses train/validation/test split:
      - Train on pre-validation data
      - Calibrate probabilities on validation set (isotonic regression)
      - Evaluate on test set
    """
    config = load_config()
    if test_year is not None:
        config["model"]["test_start_year"] = test_year
    if val_years is not None:
        config["model"]["validation_years"] = val_years

    print(f"\n{'=' * 60}")
    print(f"  MODEL TRAINING - {tour.upper()}")
    print(f"{'=' * 60}")

    # Load features
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    if not features_path.exists():
        print(f"  [X] Features non trovate: {features_path}")
        print("  --> Esegui prima: python -m src.features.build_features")
        return None, None

    df = pd.read_csv(features_path, low_memory=False)

    # Prepare and Randomize data (now returns train + val + test)
    x_train, p_train, y_train_all, x_val, p_val, y_val_all, x_test, p_test, y_test_all, scaler, feature_names, medians, player_mapping = prepare_training_data(df, config, tour=tour)

    y_train = y_train_all[target_col]
    y_val = y_val_all[target_col]
    y_test = y_test_all[target_col]

    # Check if target is discrete (Classification) or continuous (Regression)
    is_regression = target_col in ["game_diff", "total_games"]

    # --- Odds segment specialist (E4) ---
    masks_train = {"odds": df.loc[x_train.index, "has_odds"] == 1, "blind": df.loc[x_train.index, "has_odds"] == 0}
    masks_val = {"odds": df.loc[x_val.index, "has_odds"] == 1, "blind": df.loc[x_val.index, "has_odds"] == 0}
    masks_test = {"odds": df.loc[x_test.index, "has_odds"] == 1, "blind": df.loc[x_test.index, "has_odds"] == 0}

    all_models = {}
    all_results = {}
    routed = _RoutedPredictions(len(x_test), is_regression)

    for segment in ["odds", "blind"]:
        m_tr, m_v, m_te = masks_train[segment], masks_val[segment], masks_test[segment]
        if m_tr.sum() == 0:
            continue

        seg_models, seg_results = _train_segment(
            target_col, segment, config, is_regression,
            x_train[m_tr], y_train[m_tr], p_train[m_tr],
            x_val[m_v], y_val[m_v], p_val[m_v],
            x_test[m_te], y_test[m_te], p_test[m_te],
            player_mapping
        )
        all_models.update(seg_models)
        all_results.update(seg_results)
        # the segment ensemble is what the routed model uses in production
        routed.record(seg_models.get(f"{target_col}_{segment}_ensemble"),
                      x_test, m_te)

    if len(x_test) > 0:
        print(f"\n{'=' * 60}")
        print(f"  COMBINED ROUTED PERFORMANCE (Test Set) - {target_col.upper()}")
        print(f"{'=' * 60}")
        all_results[f"{target_col}_routed_ensemble"] = routed.score(y_test)

    models_dir = Path(save_dir) if save_dir else PROJECT_ROOT / config["paths"]["models"]
    _save_artifacts(models_dir, tour, all_models, feature_names, player_mapping,
                    scaler, medians)
    if not is_regression and all_results:
        _save_metrics(models_dir, tour, target_col, all_results)

    print(f"\n  [OK] Modelli calibrati e metadati salvati in: {models_dir}")
    return all_models, all_results



def _expected_calibration_error(y_true, y_prob, n_bins=10):
    """Compute Expected Calibration Error (ECE).
    Lower is better. Perfect calibration = 0.0.
    """
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if i == n_bins - 1:
            mask = mask | (y_prob == bin_edges[i + 1])
        n_in_bin = mask.sum()
        if n_in_bin == 0:
            continue
        avg_confidence = y_prob[mask].mean()
        avg_accuracy = y_true[mask].mean()
        ece += (n_in_bin / len(y_true)) * abs(avg_accuracy - avg_confidence)
    return ece


def _evaluate_model(model, x_test, y_test, name, is_regression=False):
    """Evaluate a single model and return metrics including ECE for classifiers."""
    if is_regression:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        y_pred = model.predict(x_test)
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        print(f"    [{name}] MAE: {mae:.4f} | MSE: {mse:.4f} | R2: {r2:.4f}")
        return {"mae": mae, "mse": mse, "r2": r2}
    else:
        y_pred = model.predict(x_test)
        y_prob = model.predict_proba(x_test)[:, 1]
        y_true = np.array(y_test)
        acc = accuracy_score(y_true, y_pred)
        ll = log_loss(y_true, y_prob)
        brier = brier_score_loss(y_true, y_prob)
        roc = roc_auc_score(y_true, y_prob)
        ece = _expected_calibration_error(y_true, y_prob)
        print(f"    [{name}] Accuracy: {acc:.4f} | Log Loss: {ll:.4f} | ROC AUC: {roc:.4f} | ECE: {ece:.4f}")
        return {"accuracy": acc, "log_loss": ll, "brier": brier, "roc_auc": roc, "ece": ece}


if __name__ == "__main__":
    # Train all three models for both tours
    for tour in ["atp", "wta"]:
        for target in ["target", "game_diff", "total_games"]:
            train_models(tour=tour, target_col=target)

    print("\n  [OK] Multi-Market Training completato!")

    # Generate live engines required for release bundle and inference
    from src.live.warm_up import warm_up
    warm_up()
