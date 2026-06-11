import pandas as pd
import numpy as np
import optuna
import lightgbm as lgb
import xgboost as xgb
from sklearn.metrics import log_loss, accuracy_score
from pathlib import Path
import yaml
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

def load_data():
    """Load data using the main pipeline's train/val/test split.
    Returns train + validation sets for tuning.
    The TEST set is NEVER used during tuning to avoid data leakage.
    """
    from src.models.train import prepare_training_data, load_config
    features_path = PROJECT_ROOT / "data" / "features" / "atp_features.csv"
    if not features_path.exists():
        raise FileNotFoundError(f"Feature matrix not found: {features_path}")

    df = pd.read_csv(features_path)
    config = load_config()

    # New signature: train, val, test
    X_train, y_train_all, X_val, y_val_all, X_test, y_test_all, scaler, numeric_cols, medians = prepare_training_data(df, config)

    y_train = y_train_all["target"]
    y_val = y_val_all["target"]

    return X_train, y_train, X_val, y_val

def objective_lgb(trial, X_train, y_train, X_val, y_val):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'verbosity': -1,
        'boosting_type': 'gbdt',
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'learning_rate': trial.suggest_float('learning_rate', 1e-3, 0.1, log=True),
        'num_leaves': trial.suggest_int('num_leaves', 10, 150),
        'max_depth': trial.suggest_int('max_depth', 3, 12),
        'min_child_samples': trial.suggest_int('min_child_samples', 20, 200),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }

    model = lgb.LGBMClassifier(**params, random_state=42, n_jobs=-1)

    # Early stopping on VALIDATION set (not test set)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )

    # Evaluate on VALIDATION set (same set used for early stopping is OK for Optuna
    # because we have a separate held-out test set for final evaluation)
    preds = model.predict_proba(X_val)[:, 1]
    loss = log_loss(y_val, preds)
    return loss

def objective_xgb(trial, X_train, y_train, X_val, y_val):
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'learning_rate': trial.suggest_float('learning_rate', 1e-3, 0.1, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 15),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
        'gamma': trial.suggest_float('gamma', 1e-8, 1.0, log=True),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }

    model = xgb.XGBClassifier(**params, early_stopping_rounds=50, random_state=42, n_jobs=-1)

    # Early stopping on VALIDATION set (not test set)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )

    preds = model.predict_proba(X_val)[:, 1]
    loss = log_loss(y_val, preds)
    return loss


def tune_models():
    print("[TUNE] Avviando Hyperparameter Tuning con Optuna...")
    X_train, y_train, X_val, y_val = load_data()
    print(f"Dati caricati. Train shape: {X_train.shape}, Val shape: {X_val.shape}")
    print(f"[TUNE] NOTA: Test set NON usato durante il tuning (anti data-leakage)")

    # Ottimizzazione LightGBM
    print("\n[TUNE] Tuning LightGBM...")
    study_lgb = optuna.create_study(direction='minimize', study_name="LGBM_Tennis")
    study_lgb.optimize(lambda trial: objective_lgb(trial, X_train, y_train, X_val, y_val), n_trials=15)

    print(f"Miglior LogLoss LightGBM: {study_lgb.best_value:.4f}")
    print(f"Parametri ottimali: {study_lgb.best_params}")

    # Ottimizzazione XGBoost
    print("\n[TUNE] Tuning XGBoost...")
    study_xgb = optuna.create_study(direction='minimize', study_name="XGB_Tennis")
    study_xgb.optimize(lambda trial: objective_xgb(trial, X_train, y_train, X_val, y_val), n_trials=10)

    print(f"Miglior LogLoss XGBoost: {study_xgb.best_value:.4f}")
    print(f"Parametri ottimali: {study_xgb.best_params}")

    # Salva i parametri
    best_params = {
        'lightgbm_tuned': study_lgb.best_params,
        'xgboost_tuned': study_xgb.best_params,
        'logloss': {
            'lightgbm': float(study_lgb.best_value),
            'xgboost': float(study_xgb.best_value)
        }
    }

    opt_path = PROJECT_ROOT / "config" / "best_params.yaml"
    with open(opt_path, "w") as f:
        yaml.dump(best_params, f)

    print(f"\n[OK] Tuning completato. Parametri salvati in: {opt_path}")

if __name__ == "__main__":
    tune_models()
