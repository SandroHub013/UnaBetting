import pandas as pd
import numpy as np

def _randomize_perspective(X, y):
    n = len(X)
    flip_mask = np.random.random(n) > 0.5
    X_flipped = X.copy()
    y_flipped = y.copy()
    
    # Prefix-based swap
    cols = list(X.columns)
    for cw in cols:
        if cw.startswith("w_"):
            cl = "l_" + cw[2:]
            if cl in cols:
                X_flipped.loc[flip_mask, cw], X_flipped.loc[flip_mask, cl] = \
                    X.loc[flip_mask, cl], X.loc[flip_mask, cw]
        elif cw.endswith("W"):
            cl = cw[:-1] + "L"
            if cl in cols:
                X_flipped.loc[flip_mask, cw], X_flipped.loc[flip_mask, cl] = \
                    X.loc[flip_mask, cl], X.loc[flip_mask, cw]
                    
    y_flipped.loc[flip_mask] = 1 - y.loc[flip_mask]
    return X_flipped, y_flipped, flip_mask

# Test data
data = {
    "w_elo": [2000, 2100, 2200, 2300],
    "l_elo": [1500, 1600, 1700, 1800],
    "AvgW": [1.5, 1.4, 1.3, 1.2],
    "AvgL": [2.5, 2.6, 2.7, 2.8],
    "target": [1, 1, 1, 1]
}
df = pd.DataFrame(data)
X = df.drop(columns=["target"])
y = df["target"]

X_r, y_r, mask = _randomize_perspective(X, y)

print("Mask (True = Flipped):", mask)
print("\nOriginal X:\n", X)
print("\nRandomized X:\n", X_r)
print("\nRandomized y:\n", y_r)

# Check correlation: if randomization worked, correlation should be low
print("\nCorrelations with y_r:")
print(X_r.corrwith(y_r))
