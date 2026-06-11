
import pandas as pd
import numpy as np
import yaml
import joblib
from pathlib import Path
from src.models.train import prepare_training_data
import xgboost as xgb
from sklearn.metrics import accuracy_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def run_shuffle_test():
    print("\n" + "="*60)
    print("🕵️ SHUFFLE CONTROL TEST")
    print("="*60)
    
    config = load_config()
    tour = "atp"
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    df = pd.read_csv(features_path, low_memory=False)
    
    # SHUFFLE the target column to break any real relationship
    print("⚠️  SHUFFLING TARGET (Randomizing matches with 50/50 probability)...")
    df['target'] = np.random.choice([0, 1], size=len(df))
    
    # Prepare data
    X_train, y_train, _X_val, _y_val, X_test, y_test, scaler, feature_names, _medians = prepare_training_data(df, config)
    
    # Train XGBoost
    print("\n🚀 Training model on GARBAGE data...")
    model = xgb.XGBClassifier(n_estimators=100, max_depth=6, random_state=42, eval_metric="logloss")
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"\n📊 RESULT:")
    print(f"   Accuracy on SHUFFLED data: {acc:.4f}")
    
    # Check importance
    importances = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\n🔍 TOP IMPORTANCES (ON SHUFFLED DATA):")
    print(importances.head(10))
    
    if acc > 0.55:
        print("\n🚨 LEAKAGE DETECTED! Accuratezza sospetta su dati casuali.")
        print("   Il modello sta leggendo il risultato da qualche feature.")
    else:
        print("\n✅ NO LEAKAGE IN FEATURE STRUCTURE.")
        print("   L'accuratezza del 77% era basata su segnali reali.")

if __name__ == "__main__":
    run_shuffle_test()
