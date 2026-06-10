import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from src.models.train import load_config, prepare_training_data

config = load_config()
df = pd.read_csv('G:/tennis betting/data/features/atp_features.csv', low_memory=False)
X_train, y_train, _X_val, _y_val, X_test, y_test, _, feature_names, _medians = prepare_training_data(df, config)

print(f"Testing {len(feature_names)} features individually...\n")
print(f"Target distribution (y_test):")
print(y_test.value_counts(normalize=True))

results = []
for feat in feature_names:
    model = LogisticRegression(max_iter=100)
    # Reshape for single feature
    X_f_train = X_train[[feat]]
    X_f_test = X_test[[feat]]
    
    # Check mean - it should be near zero for 'diff_' features if randomization worked
    f_mean = X_f_test[feat].mean()
    
    model.fit(X_f_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_f_test))
    results.append((feat, acc, f_mean))

results.sort(key=lambda x: x[1], reverse=True)

print(f"{'Feature':<30} {'Accuracy':>10} {'Mean':>10}")
print("-" * 52)
for feat, acc, f_mean in results[:20]:
    print(f"{feat:<30} {acc:>10.4f} {f_mean:>10.4f}")
