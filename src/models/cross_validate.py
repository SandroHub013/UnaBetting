
import pandas as pd
import numpy as np
import yaml
import joblib
from pathlib import Path
from src.models.train import prepare_training_data, _evaluate_model
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def run_cross_validation():
    print("\n" + "="*60)
    print("🕒 TIME-SERIES CROSS VALIDATION (Walk-Forward)")
    print("="*60)
    
    config = load_config()
    tour = "atp"
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    df = pd.read_csv(features_path, low_memory=False)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    
    # Define folds: (Train End Year, Test Year) - Walk-Forward 5 folds
    folds = [
        (2019, 2020),
        (2020, 2021),
        (2021, 2022),
        (2022, 2023),
        (2023, 2024),
    ]
    
    cv_results = []
    
    for train_end, test_year in folds:
        print(f"\n📂 FOLD: Train until {train_end}, Test in {test_year}")
        
        # Temporary override for prepare_training_data.
        # CRITICAL: clear validation_years so the internal split is
        #   train = year < test_year   (no fixed 2023 cut),
        #   test  = year >= test_year.
        # Otherwise train stays pinned to year<2023 and OVERLAPS the test window
        # on early folds (e.g. test=2020 shared ~6.9k rows) — self-prediction.
        import copy
        temp_config = copy.deepcopy(config)
        temp_config["model"]["test_start_year"] = test_year
        temp_config["model"]["validation_years"] = []

        # Prepare data for this specific split (9-value return: train, val, test, scaler, features, medians)
        X_train, y_train, _X_val, _y_val, X_test, y_test, scaler, feature_names, medians = prepare_training_data(df, temp_config)

        # Walk-forward: test ONLY on test_year (not all future years).
        year_of = df["tourney_date"].dt.year
        test_year_mask = X_test.index.map(year_of) == test_year
        X_test = X_test[test_year_mask]
        y_test = y_test[test_year_mask]

        # Sanity: train and test must not share any rows.
        assert len(X_train.index.intersection(X_test.index)) == 0, "CV fold leakage: train/test overlap"

        # Extract only the H2H target (binary classification)
        y_tr = y_train["target"] if isinstance(y_train, pd.DataFrame) else y_train
        y_te = y_test["target"] if isinstance(y_test, pd.DataFrame) else y_test

        # Train XGBoost (Standard params)
        model = xgb.XGBClassifier(n_estimators=100, max_depth=6, random_state=42, eval_metric="logloss")
        model.fit(X_train, y_tr)

        # Evaluate
        res = _evaluate_model(model, X_test, y_te, f"Fold {test_year}")
        res['year'] = test_year
        cv_results.append(res)
        
    cv_df = pd.DataFrame(cv_results)
    
    print("\n" + "="*60)
    print("📊 FINAL CV SUMMARY")
    print("="*60)
    print(cv_df[['year', 'accuracy', 'log_loss', 'roc_auc']])
    print(f"\nMean Accuracy: {cv_df['accuracy'].mean():.4f}")
    print(f"Mean Log Loss: {cv_df['log_loss'].mean():.4f}")

if __name__ == "__main__":
    run_cross_validation()
