import optuna
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import log_loss
import json
from src.models.train import prepare_training_data, load_config

def objective(trial):
    config = load_config()
    df = pd.read_csv("data/features/atp_features.csv", low_memory=False)
    
    (X_train_scaled, P_train, y_train_all, 
     X_val_scaled, P_val, y_val_all, 
     X_test_scaled, P_test, y_test_all, 
     scaler, numeric_cols, medians, player_mapping) = prepare_training_data(df, config, skip_selection=False)
    
    y_train = y_train_all["target"]
    y_val = y_val_all["target"]
    
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "boosting_type": "gbdt",
        "num_leaves": trial.suggest_int("num_leaves", 10, 50),
        "max_depth": trial.suggest_int("max_depth", 3, 7),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 0.8),
        "random_state": 42,
        "verbose": -1
    }
    
    model = lgb.LGBMClassifier(**params)
    model.fit(X_train_scaled, y_train)
    
    preds = model.predict_proba(X_val_scaled)[:, 1]
    loss = log_loss(y_val, preds)
    return loss

if __name__ == "__main__":
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=50)
    
    print("Migliori parametri:", study.best_params)
    with open("models/best_params.json", "w") as f:
        json.dump(study.best_params, f, indent=4)
