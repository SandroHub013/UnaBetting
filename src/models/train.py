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

from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, log_loss, brier_score_loss,
    classification_report, roc_auc_score
)
from sklearn.calibration import CalibratedClassifierCV

import torch
from torch.utils.data import Dataset, DataLoader
from src.models.pytorch_ensemble import TennisEmbeddingNet, TennisTransformerNet, train_tennis_model

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
            return np.average(preds, axis=1, weights=self.weights)
        else:
            return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)
            
    def predict_proba(self, X):
        probs = np.array([m.predict_proba(X) for m in self.models])
        return np.average(probs, axis=0, weights=self.weights)


# Pickle identity across entrypoints. When this file runs as
# `python -m src.models.train` the class lives in __main__; live inference imports
# it as src.models.train. Forcing __module__ alone makes pickle look up
# src.models.train.PreFittedEnsemble and compare identity — which fails ("not the
# same object") if src.models.train is loaded as a SEPARATE module during the run.
# Alias the running module under the canonical name so the class object is
# identical on both save (training) and load (inference).
import sys as _sys
PreFittedEnsemble.__module__ = "src.models.train"
_canon = _sys.modules.get("src.models.train")
if _canon is None:
    _sys.modules["src.models.train"] = _sys.modules[__name__]
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


def prepare_training_data(features_df, config, skip_selection=False):
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

    # Identifica le colonne delle feature (escludendo metadati, target e ODDS)
    meta_cols = ["tourney_date", "tourney_name", "surface", "tourney_level",
                 "winner_name", "loser_name", "winner_id", "loser_id", "score",
                 "target", "game_diff", "total_games"]

    odds_cols = [c for c in df.columns if any(
        bk in c.upper() for bk in ["B365", "PS", "MAX", "AVG"]
    )]
    meta_cols.extend(odds_cols)

    feature_cols = [c for c in df.columns if c not in meta_cols]

    # --- Feature Selection (Optimization) ---
    if not skip_selection:
        selection_path = PROJECT_ROOT / "config" / "selected_features_atp.txt"
        if selection_path.exists():
            with open(selection_path, "r") as f:
                selected = [line.strip() for line in f if line.strip()]

            # Filter feature_cols to only those in the selection list
            original_count = len(feature_cols)
            feature_cols = [c for c in feature_cols if c in selected]
            if len(feature_cols) < original_count:
                print(f"  [+] Feature Selection: Ridotte da {original_count} a {len(feature_cols)}")

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

    year_col = df["tourney_date"].dt.year

    if val_years:
        val_start = min(val_years)
        train_mask = year_col < val_start
        val_mask = year_col.isin(val_years)
        test_mask = year_col >= test_year
    else:
        # Fallback: no separate validation set
        train_mask = year_col < test_year
        val_mask = pd.Series(False, index=df.index)
        test_mask = year_col >= test_year

    X_train = df.loc[train_mask, feature_cols].copy()
    y_train = df.loc[train_mask, y_cols].copy()
    X_val = df.loc[val_mask, feature_cols].copy()
    y_val = df.loc[val_mask, y_cols].copy()
    X_test = df.loc[test_mask, feature_cols].copy()
    y_test = df.loc[test_mask, y_cols].copy()

    # Remove any non-numeric columns that slipped through
    numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()
    X_train = X_train[numeric_cols]
    X_val = X_val[numeric_cols]
    X_test = X_test[numeric_cols]

    # Impute missing values using TRAIN-ONLY medians (no look-ahead leakage).
    # Computed BEFORE fillna so the saved medians reflect true train distribution.
    # fillna(0.0) guards features that are all-NaN within the train window.
    medians_series = X_train.median().fillna(0.0)
    X_train = X_train.fillna(medians_series)
    X_val = X_val.fillna(medians_series)
    X_test = X_test.fillna(medians_series)

    # Scale features (fit on train only). Guard empty splits: sklearn's
    # transform rejects 0-row arrays, but an empty validation set is valid
    # (e.g. walk-forward CV passes validation_years=[]).
    scaler = StandardScaler()

    def _scale(X, fit=False):
        if len(X) == 0:
            return pd.DataFrame(columns=X.columns, index=X.index)
        arr = scaler.fit_transform(X) if fit else scaler.transform(X)
        return pd.DataFrame(arr, columns=X.columns, index=X.index)

    X_train_scaled = _scale(X_train, fit=True)
    X_val_scaled = _scale(X_val)
    X_test_scaled = _scale(X_test)

    # PyTorch Player IDs preparation
    # Extract IDs based on the randomized target
    p1_raw = np.where(df["target"] == 1, df["winner_id"], df["loser_id"])
    p2_raw = np.where(df["target"] == 1, df["loser_id"], df["winner_id"])
    
    # Fit mapping on train set only to avoid leakage
    train_players = np.unique(np.concatenate([p1_raw[train_mask], p2_raw[train_mask]]))
    # 0 is UNK
    player_mapping = {pid: i + 1 for i, pid in enumerate(train_players)}
    
    def map_players(p_raw):
        return np.array([player_mapping.get(p, 0) for p in p_raw])
        
    df["p1_id"] = map_players(p1_raw)
    df["p2_id"] = map_players(p2_raw)
    
    P_train = df.loc[train_mask, ["p1_id", "p2_id"]].copy()
    P_val = df.loc[val_mask, ["p1_id", "p2_id"]].copy()
    P_test = df.loc[test_mask, ["p1_id", "p2_id"]].copy()

    val_start_str = f"{min(val_years)}-{max(val_years)}" if val_years else "N/A"
    print(f"  [+] Training: {len(X_train):,} partite (prima del {val_start if val_years else test_year})")
    print(f"  [+] Validation: {len(X_val):,} partite ({val_start_str}) -- per calibrazione")
    print(f"  [+] Test: {len(X_test):,} partite (dal {test_year})")
    print(f"  [+] Features: {len(numeric_cols)} colonne")
    print(f"  [+] Giocatori univoci: {len(player_mapping)}")
    if len(X_test) < 200:
        print(f"  [!] WARNING: Test set molto piccolo ({len(X_test)} match). Considera di abbassare test_start_year.")

    # Train-only medians for live imputation alignment (computed pre-fillna above)
    medians = medians_series.to_dict()

    return X_train_scaled, P_train, y_train, X_val_scaled, P_val, y_val, X_test_scaled, P_test, y_test, scaler, numeric_cols, medians, player_mapping


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


def _randomize_perspective(X, y, seed=42):
    """
    Randomly swap player 1 and player 2 to avoid the model learning
    that player 1 always wins. Flips ~50% of rows.
    Uses a fixed seed for reproducibility — model, scaler, and medians
    must all come from the same randomization.
    """
    _assert_no_unpaired_perspective(X.columns)

    n = len(X)
    rng = np.random.RandomState(seed)
    flip_mask = rng.random(n) > 0.5

    X_flipped = X.copy()
    y_flipped = y.copy()

    # Swap w_ and l_ prefixed features
    w_cols = [c for c in X.columns if c.startswith("w_")]
    for wc in w_cols:
        lc = "l_" + wc[2:]
        if lc in X.columns:
            # ATOMIC SWAP using .values to avoid alignment issues
            X_flipped.loc[flip_mask, [wc, lc]] = X.loc[flip_mask, [lc, wc]].values

    # Flip diff_ features
    diff_cols = [c for c in X.columns if c.startswith("diff_")]
    for dc in diff_cols:
        X_flipped.loc[flip_mask, dc] = -X.loc[flip_mask, dc]

    # Flip rank_diff, age_diff, height_diff
    for col in ["rank_diff", "rank_ratio", "age_diff", "height_diff"]:
        if col in X.columns:
            if col == "rank_ratio":
                # For ratios, flip means inversion (1/x)
                X_flipped.loc[flip_mask, col] = 1.0 / X.loc[flip_mask, col]
            else:
                X_flipped.loc[flip_mask, col] = -X.loc[flip_mask, col]
                
    # Swap betting odds (e.g., B365W <-> B365L, MaxW <-> MaxL)
    all_cols = list(X.columns)
    for cw in all_cols:
        # Avoid re-swapping columns already handled by w_/l_ logic
        if cw.endswith("W") and not cw.startswith(("w_", "l_", "diff_")):
            cl = cw[:-1] + "L"
            if cl in all_cols:
                X_flipped.loc[flip_mask, [cw, cl]] = X.loc[flip_mask, [cl, cw]].values

    # Flip ELO win probabilities
    for col in ["elo_win_prob", "elo_surface_win_prob"]:
        if col in X.columns:
            X_flipped.loc[flip_mask, col] = 1.0 - X.loc[flip_mask, col]

    # Flip target H2H
    if hasattr(y, 'columns') and "target" in y.columns:
        y_flipped.loc[flip_mask, "target"] = 1 - y.loc[flip_mask, "target"]
    elif "target" == y.name:
        # y is a Series with name "target"
        y_flipped = y_flipped.copy()
        y_flipped.loc[flip_mask] = 1 - y_flipped.loc[flip_mask]

    # Flip game_diff (Winner Games - Loser Games becomes Loser - Winner)
    if hasattr(y, 'columns') and "game_diff" in y.columns:
        y_flipped.loc[flip_mask, "game_diff"] = -y.loc[flip_mask, "game_diff"]
        
    # total_games is invariant (P1 games + P2 games)

    return X_flipped, y_flipped


def _calibrate_classifier(model, X_val, y_val, name, method="isotonic"):
    """Wrap a trained classifier with calibration using the validation set."""
    try:
        calibrated = CalibratedClassifierCV(model, method=method, cv="prefit")
        calibrated.fit(X_val, y_val)
        print(f"    [CAL] {name}: calibrazione {method} applicata su {len(X_val)} match")
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


def _train_segment(target_col, segment, config, is_regression, X_train, y_train, P_train, X_val, y_val, P_val, X_test, y_test, P_test, feature_names, player_mapping, tour):
    has_val = len(X_val) > 0
    print(f"\n2. Training modelli {segment.upper()} per {target_col}...")
    models = {}
    raw_models = {}  # uncalibrated, for feature importance
    results = {}

    # --- Logistic Regression / Linear Regression ---
    if is_regression:
        from sklearn.linear_model import Ridge
        print(f"\n  [>] Ridge Regression for {target_col} ({segment})...")
        model_lr = Ridge(alpha=1.0)
    else:
        model_lr = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
        print(f"\n  [>] Logistic Regression for {target_col} ({segment})...")

    if len(X_train) > 0:
        model_lr.fit(X_train, y_train)
        raw_models[f"{target_col}_{segment}_lr"] = model_lr
        if not is_regression and has_val:
            model_lr = _calibrate_classifier(model_lr, X_val, y_val, "LR")
        models[f"{target_col}_{segment}_lr"] = model_lr
        if len(X_test) > 0:
            results[f"{target_col}_{segment}_lr"] = _evaluate_model(model_lr, X_test, y_test, f"LR {target_col} {segment}", is_regression)

    # --- Random Forest ---
    if is_regression:
        from sklearn.ensemble import RandomForestRegressor
        print(f"\n  [>] Random Forest Regressor for {target_col} ({segment})...")
        rf = RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=20, random_state=42, n_jobs=-1)
    else:
        print(f"\n  [>] Random Forest Classifier for {target_col} ({segment})...")
        rf = RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=20, random_state=42, n_jobs=-1)

    if len(X_train) > 0:
        rf.fit(X_train, y_train)
        raw_models[f"{target_col}_{segment}_rf"] = rf
        if not is_regression and has_val:
            rf = _calibrate_classifier(rf, X_val, y_val, "RF")
        models[f"{target_col}_{segment}_rf"] = rf
        if len(X_test) > 0:
            results[f"{target_col}_{segment}_rf"] = _evaluate_model(rf, X_test, y_test, f"RF {target_col} {segment}", is_regression)

    # --- XGBoost ---
    if HAS_XGB:
        print(f"\n  [>] XGBoost for {target_col} ({segment})...")
        xgb_params = config["model"]["xgboost"]
        if is_regression:
            xgb_model = xgb.XGBRegressor(**xgb_params, random_state=42, objective='reg:absoluteerror')
        else:
            xgb_model = xgb.XGBClassifier(**xgb_params, random_state=42, eval_metric="logloss")

        if len(X_train) > 0:
            xgb_model.fit(X_train, y_train)
            raw_models[f"{target_col}_{segment}_xgboost"] = xgb_model
            if not is_regression and has_val:
                xgb_model = _calibrate_classifier(xgb_model, X_val, y_val, "XGB", method="sigmoid")
            models[f"{target_col}_{segment}_xgboost"] = xgb_model
            if len(X_test) > 0:
                results[f"{target_col}_{segment}_xgboost"] = _evaluate_model(xgb_model, X_test, y_test, f"XGB {target_col} {segment}", is_regression)

    # --- LightGBM ---
    if HAS_LGB:
        print(f"\n  [>] LightGBM for {target_col} ({segment})...")
        lgb_params = config["model"]["lightgbm"]
        if is_regression:
            lgb_model = lgb.LGBMRegressor(**lgb_params, random_state=42, verbose=-1, objective='regression_l1')
        else:
            lgb_model = lgb.LGBMClassifier(**lgb_params, random_state=42, verbose=-1)

        if len(X_train) > 0:
            lgb_model.fit(X_train, y_train)
            raw_models[f"{target_col}_{segment}_lightgbm"] = lgb_model
            if not is_regression and has_val:
                lgb_model = _calibrate_classifier(lgb_model, X_val, y_val, "LGB")
            models[f"{target_col}_{segment}_lightgbm"] = lgb_model
            if len(X_test) > 0:
                results[f"{target_col}_{segment}_lightgbm"] = _evaluate_model(lgb_model, X_test, y_test, f"LGB {target_col} {segment}", is_regression)

    # --- Ensemble ---
    if len(X_train) > 0 and len(X_test) > 0:
        if is_regression:
            print(f"\n  [>] Ensemble (Averaging) for {target_col} ({segment})...")
            estimators = [models[f"{target_col}_{segment}_rf"]]
            if HAS_XGB: estimators.append(models[f"{target_col}_{segment}_xgboost"])
            if HAS_LGB: estimators.append(models[f"{target_col}_{segment}_lightgbm"])
            ensemble = PreFittedEnsemble(estimators, is_regression=True)
        else:
            print(f"\n  [>] Ensemble (Softmax -LL Voting) for {target_col} ({segment})...")
            estimators = [models[f"{target_col}_{segment}_lr"], models[f"{target_col}_{segment}_rf"]]
            if HAS_XGB: estimators.append(models[f"{target_col}_{segment}_xgboost"])
            if HAS_LGB: estimators.append(models[f"{target_col}_{segment}_lightgbm"])
            
            weights = None
            if has_val:
                lls = []
                for m in estimators:
                    preds = m.predict_proba(X_val)
                    ll = log_loss(y_val, preds)
                    lls.append(ll)
                neg_lls = -np.array(lls)
                exp_neg_lls = np.exp(neg_lls - np.max(neg_lls))
                weights = exp_neg_lls / exp_neg_lls.sum()
                
            ensemble = PreFittedEnsemble(estimators, is_regression=False, weights=weights)

        models[f"{target_col}_{segment}_ensemble"] = ensemble
        results[f"{target_col}_{segment}_ensemble"] = _evaluate_model(ensemble, X_test, y_test, f"Ensemble {target_col} {segment}", is_regression)

    # --- PyTorch Embedding Net ---
    if not is_regression and len(X_train) > 0:
        print(f"\n  [>] PyTorch Embedding Net for {target_col} ({segment})...")
        train_dataset = TennisDataset(P_train['p1_id'], P_train['p2_id'], X_train, y_train)
        val_dataset = TennisDataset(P_val['p1_id'], P_val['p2_id'], X_val, y_val)
        
        train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)
        
        num_players = len(player_mapping) + 1
        emb_dim = 32
        num_features = X_train.shape[1]
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        nn_model = TennisTransformerNet(num_players, emb_dim, num_features).to(device)
        
        nn_model = train_tennis_model(nn_model, train_loader, val_loader, epochs=10, lr=0.001)
        models[f"{target_col}_{segment}_pytorch"] = nn_model
        
        if len(X_test) > 0:
            nn_model.eval()
            test_dataset = TennisDataset(P_test['p1_id'], P_test['p2_id'], X_test, y_test)
            test_loader = DataLoader(test_dataset, batch_size=256, shuffle=False)
            
            y_prob_pt = []
            with torch.no_grad():
                for batch in test_loader:
                    p1_ids = batch['p1_id'].to(device)
                    p2_ids = batch['p2_id'].to(device)
                    num_feats = batch['numerical_features'].to(device)
                    outputs = nn_model(p1_ids, p2_ids, num_feats)
                    y_prob_pt.extend(outputs.cpu().numpy().flatten())
            
            y_prob_pt = np.array(y_prob_pt)
            y_pred_pt = (y_prob_pt >= 0.5).astype(int)
            y_true_pt = y_test.values
            
            acc_pt = accuracy_score(y_true_pt, y_pred_pt)
            ll_pt = log_loss(y_true_pt, y_prob_pt)
            brier_pt = brier_score_loss(y_true_pt, y_prob_pt)
            roc_pt = roc_auc_score(y_true_pt, y_prob_pt)
            ece_pt = _expected_calibration_error(y_true_pt, y_prob_pt)
            
            print(f"    [PT] Accuracy: {acc_pt:.4f} | Log Loss: {ll_pt:.4f} | ROC AUC: {roc_pt:.4f} | ECE: {ece_pt:.4f}")
            results[f"{target_col}_{segment}_pytorch"] = {"accuracy": acc_pt, "log_loss": ll_pt, "brier": brier_pt, "roc_auc": roc_pt, "ece": ece_pt}
            
            if HAS_XGB:
                xgb_model = models[f"{target_col}_{segment}_xgboost"]
                y_prob_xgb = xgb_model.predict_proba(X_test)[:, 1]
                y_prob_deep = (y_prob_pt + y_prob_xgb) / 2.0
                y_pred_deep = (y_prob_deep >= 0.5).astype(int)
                
                acc_deep = accuracy_score(y_true_pt, y_pred_deep)
                ll_deep = log_loss(y_true_pt, y_prob_deep)
                brier_deep = brier_score_loss(y_true_pt, y_prob_deep)
                roc_deep = roc_auc_score(y_true_pt, y_prob_deep)
                ece_deep = _expected_calibration_error(y_true_pt, y_prob_deep)
                
                print(f"    [DEEP] Accuracy: {acc_deep:.4f} | Log Loss: {ll_deep:.4f} | ROC AUC: {roc_deep:.4f} | ECE: {ece_deep:.4f}")
                results[f"{target_col}_{segment}_deep_ensemble"] = {"accuracy": acc_deep, "log_loss": ll_deep, "brier": brier_deep, "roc_auc": roc_deep, "ece": ece_deep}

    return models, results


def train_models(tour="atp", target_col="target"):
    """
    Train all configured models for a specific target (target, game_diff, total_games).
    Uses train/validation/test split:
      - Train on pre-validation data
      - Calibrate probabilities on validation set (isotonic regression)
      - Evaluate on test set
    """
    config = load_config()
    print(f"\n{'=' * 60}")
    print(f"  MODEL TRAINING - {tour.upper()}")
    print(f"{'=' * 60}")

    # Load features
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    if not features_path.exists():
        print(f"  [X] Features non trovate: {features_path}")
        print(f"  --> Esegui prima: python -m src.features.build_features")
        return

    df = pd.read_csv(features_path, low_memory=False)

    # Prepare and Randomize data (now returns train + val + test)
    X_train, P_train, y_train_all, X_val, P_val, y_val_all, X_test, P_test, y_test_all, scaler, feature_names, medians, player_mapping = prepare_training_data(df, config)

    y_train = y_train_all[target_col]
    y_val = y_val_all[target_col]
    y_test = y_test_all[target_col]

    # Check if target is discrete (Classification) or continuous (Regression)
    is_regression = target_col in ["game_diff", "total_games"]

    # --- Odds segment specialist (E4) ---
    masks_train = {"odds": df.loc[X_train.index, "has_odds"] == 1, "blind": df.loc[X_train.index, "has_odds"] == 0}
    masks_val = {"odds": df.loc[X_val.index, "has_odds"] == 1, "blind": df.loc[X_val.index, "has_odds"] == 0}
    masks_test = {"odds": df.loc[X_test.index, "has_odds"] == 1, "blind": df.loc[X_test.index, "has_odds"] == 0}

    all_models = {}
    all_results = {}
    
    # Store predictions to compute combined metrics
    y_test_pred_combined = np.zeros(len(X_test))
    if not is_regression:
        y_test_prob_combined = np.zeros(len(X_test))

    for segment in ["odds", "blind"]:
        m_tr = masks_train[segment]
        m_v = masks_val[segment]
        m_te = masks_test[segment]
        
        if m_tr.sum() == 0:
            continue
            
        seg_models, seg_results = _train_segment(
            target_col, segment, config, is_regression,
            X_train[m_tr], y_train[m_tr], P_train[m_tr],
            X_val[m_v], y_val[m_v], P_val[m_v],
            X_test[m_te], y_test[m_te], P_test[m_te],
            feature_names, player_mapping, tour
        )
        
        all_models.update(seg_models)
        all_results.update(seg_results)
        
        # We assume 'ensemble' is the best for the combined routing
        if m_te.sum() > 0:
            best_model_key = f"{target_col}_{segment}_ensemble"
            if best_model_key in seg_models:
                m_te_idx = np.where(m_te)[0]
                if is_regression:
                    preds = seg_models[best_model_key].predict(X_test[m_te])
                    y_test_pred_combined[m_te_idx] = preds
                else:
                    preds = seg_models[best_model_key].predict(X_test[m_te])
                    probs = seg_models[best_model_key].predict_proba(X_test[m_te])[:, 1]
                    y_test_pred_combined[m_te_idx] = preds
                    y_test_prob_combined[m_te_idx] = probs

    # --- Evaluate combined routing ---
    if len(X_test) > 0:
        print(f"\n{'=' * 60}")
        print(f"  COMBINED ROUTED PERFORMANCE (Test Set) - {target_col.upper()}")
        print(f"{'=' * 60}")
        if is_regression:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            mae = mean_absolute_error(y_test, y_test_pred_combined)
            mse = mean_squared_error(y_test, y_test_pred_combined)
            r2 = r2_score(y_test, y_test_pred_combined)
            print(f"    Routed MAE: {mae:.4f} | MSE: {mse:.4f} | R2: {r2:.4f}")
            all_results[f"{target_col}_routed_ensemble"] = {"mae": mae, "mse": mse, "r2": r2}
        else:
            acc = accuracy_score(y_test, y_test_pred_combined)
            ll = log_loss(y_test, y_test_prob_combined)
            brier = brier_score_loss(y_test, y_test_prob_combined)
            roc = roc_auc_score(y_test, y_test_prob_combined)
            ece = _expected_calibration_error(np.array(y_test), y_test_prob_combined)
            print(f"    Routed Accuracy: {acc:.4f} | Log Loss: {ll:.4f} | ROC AUC: {roc:.4f} | ECE: {ece:.4f}")
            all_results[f"{target_col}_routed_ensemble"] = {"accuracy": acc, "log_loss": ll, "brier": brier, "roc_auc": roc, "ece": ece}

    # Save models (calibrated versions)
    models_dir = PROJECT_ROOT / config["paths"]["models"]
    models_dir.mkdir(parents=True, exist_ok=True)

    for name, model in all_models.items():
        if "pytorch" in name:
            model_path = models_dir / f"{tour}_{name}.pt"
            torch.save({"model": model, "feature_cols": list(feature_names), "player_mapping": player_mapping}, model_path)
        else:
            model_path = models_dir / f"{tour}_{name}.pkl"
            joblib.dump({"model": model, "feature_cols": list(feature_names)}, model_path)

    # Save scaler
    scaler_path = models_dir / f"{tour}_scaler.pkl"
    joblib.dump(scaler, scaler_path)

    # Save player mapping for PyTorch
    mapping_path = models_dir / f"{tour}_player_mapping.pkl"
    joblib.dump(player_mapping, mapping_path)

    # Save feature names (legacy txt for human inspection — artifact bundle is authoritative)
    features_meta = models_dir / f"{tour}_features.txt"
    with open(features_meta, "w") as f:
        f.write("\n".join(feature_names))

    # Save medians for inference alignment
    medians_path = models_dir / f"{tour}_medians.pkl"
    joblib.dump(medians, medians_path)

    # Save metrics for TUI ticker and dashboard
    if not is_regression and all_results:
        import json as _json
        metrics_out = {
            "routed_accuracy": float(all_results.get(f"{target_col}_routed_ensemble", {}).get("accuracy", 0)),
            "routed_ece": float(all_results.get(f"{target_col}_routed_ensemble", {}).get("ece", 0)),
            "routed_log_loss": float(all_results.get(f"{target_col}_routed_ensemble", {}).get("log_loss", 0)),
            "routed_roc_auc": float(all_results.get(f"{target_col}_routed_ensemble", {}).get("roc_auc", 0)),
            "all_models": {
                name: {k: float(v) for k, v in res.items()}
                for name, res in all_results.items()
            },
            "trained_at": datetime.now().isoformat(),
        }
        metrics_path = models_dir / f"{tour}_metrics.json"
        with open(metrics_path, "w") as mf:
            _json.dump(metrics_out, mf, indent=2)
        print(f"  [+] Metrics saved to {metrics_path}")

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


def _evaluate_model(model, X_test, y_test, name, is_regression=False):
    """Evaluate a single model and return metrics including ECE for classifiers."""
    if is_regression:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        print(f"    MAE: {mae:.4f} | MSE: {mse:.4f} | R2: {r2:.4f}")
        return {"mae": mae, "mse": mse, "r2": r2}
    else:
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        y_true = np.array(y_test)
        acc = accuracy_score(y_true, y_pred)
        ll = log_loss(y_true, y_prob)
        brier = brier_score_loss(y_true, y_prob)
        roc = roc_auc_score(y_true, y_prob)
        ece = _expected_calibration_error(y_true, y_prob)
        print(f"    Accuracy: {acc:.4f} | Log Loss: {ll:.4f} | ROC AUC: {roc:.4f} | ECE: {ece:.4f}")
        return {"accuracy": acc, "log_loss": ll, "brier": brier, "roc_auc": roc, "ece": ece}


if __name__ == "__main__":
    # Train all three models
    for target in ["target", "game_diff", "total_games"]:
        train_models(tour="atp", target_col=target)
    
    print("\n  [OK] Multi-Market Training completato!")
