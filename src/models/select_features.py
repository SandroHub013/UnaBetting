"""
Tennis Prediction Model - Feature Selection
Ranks features by importance using Random Forest and saves the top features.
"""

import pandas as pd
import numpy as np
import yaml
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Re-use prepare_training_data logic
from src.models.train import prepare_training_data, _enforce_perspective_pairs

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def run_feature_selection(tour="atp", top_k=70):
    config = load_config()
    features_path = PROJECT_ROOT / config["paths"]["features"] / f"{tour}_features.csv"
    
    if not features_path.exists():
        print(f"  ✗ Feature matrix non trovata: {features_path}")
        return

    print(f"\n{'=' * 60}")
    print(f"🔍 FEATURE SELECTION - {tour.upper()}")
    print(f"{'=' * 60}")

    df = pd.read_csv(features_path, low_memory=False)
    
    # 1. Prepare data (temporal split, etc.)
    print("1. Preparazione dati per ranking...")
    X_train, y_train, _X_val, _y_val, X_test, y_test, scaler, feature_names, _medians = prepare_training_data(df, config, skip_selection=True)
    
    # 2. Train Random Forest for importance
    print(f"2. Calcolo importanza via Random Forest (300 alberi)...")
    rf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    
    # 3. Rank features
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    ranked_features = [feature_names[i] for i in indices]
    ranked_scores = [importances[i] for i in indices]
    
    # 4. Save results
    print(f"3. Selezione delle top {top_k} feature...")
    selected = ranked_features[:top_k]

    # Enforce perspective-pair completeness: an unpaired w_X / *W feature leaks
    # the winner perspective through randomization (see train._enforce_perspective_pairs).
    selected = _enforce_perspective_pairs(selected, feature_names)

    output_path = PROJECT_ROOT / "config" / f"selected_features_{tour}.txt"
    with open(output_path, "w") as f:
        f.write("\n".join(selected))
    
    print(f"  ✓ {top_k} feature salvate in: {output_path}")
    
    # Print Top 20 for visibility
    print("\n🔥 TOP 20 FEATURES:")
    for i in range(20):
        print(f"  {i+1}. {ranked_features[i]}: {ranked_scores[i]:.4f}")

    return selected

if __name__ == "__main__":
    run_feature_selection(tour="atp", top_k=70)
