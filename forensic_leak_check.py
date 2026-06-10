import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from src.models.train import prepare_training_data, load_config

# Load data and model
config = load_config()
features_path = 'G:/tennis betting/data/features/atp_features.csv'
df = pd.read_csv(features_path, low_memory=False)

# Prepare data (this includes randomization)
X_train, y_train, _X_val, _y_val, X_test, y_test, scaler, feature_names, _medians = prepare_training_data(df, config)

# Load the best model (let's use XGBoost if available, else LR)
model_path = 'G:/tennis betting/models/atp_xgboost.pkl'
if not Path(model_path).exists():
    model_path = 'G:/tennis betting/models/atp_logistic_regression.pkl'

print(f"Loading model: {model_path}")
model = joblib.load(model_path)

# Predict probabilities
probs = model.predict_proba(X_test)[:, 1]

# Find extremely certain predictions
certain_mask = (probs > 0.999) | (probs < 0.001)
if certain_mask.any():
    print(f"Found {certain_mask.sum()} matches with >99.9% certainty!")
    
    # Get indices of the most certain matches
    idx = np.where(certain_mask)[0][:5]
    
    for i in idx:
        p = probs[i]
        actual = y_test.iloc[i]
        print(f"\n--- CERTAIN MATCH (Prob: {p:.6f}, Actual: {actual}) ---")
        
        # Get feature values for this match
        row = X_test.iloc[i]
        top_feats = row.abs().sort_values(ascending=False).head(20)
        print("Top features (absolute scaled values):")
        for f, v in top_feats.items():
            print(f"  {f:<30}: {v:.4f}")
else:
    print("No extremely certain matches found. The model is at least a bit uncertain.")
