"""Part 2: prove the backtest predictions are degenerate (no scaler) and
compute honest predictions with the proper pipeline (train medians + scaler)."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path("G:/tennis betting")

df = pd.read_csv(ROOT / "data/features/atp_features.csv", low_memory=False)
df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
test_df = df[df["tourney_date"].dt.year >= 2025].copy().sort_values("tourney_date")
test_df = test_df.dropna(subset=["w_implied_prob", "l_implied_prob"])

model_data = joblib.load(ROOT / "models/atp_target_xgboost.pkl")
model = model_data["model"]
features = model_data["feature_cols"]
scaler = joblib.load(ROOT / "models/atp_scaler.pkl")
medians = joblib.load(ROOT / "models/atp_medians.pkl")

X_raw = test_df[features].copy()

# --- A) backtest.py path: raw values, test-median fillna, NO scaler ---
X_bt = X_raw.fillna(X_raw.median())
p_bt = model.predict_proba(X_bt)[:, 1]
print("A) backtest.py path (no scaler, test medians):")
print(f"   p1-win share: {(p_bt > 0.5).mean():.4f}  mean={p_bt.mean():.4f}  "
      f"std={p_bt.std():.4f}  min={p_bt.min():.3f} max={p_bt.max():.3f}")

# --- B) proper path: train medians + scaler, winner-POV rows ---
med = pd.Series(medians)
X_p = X_raw.fillna(med.reindex(features))
X_p = pd.DataFrame(scaler.transform(X_p), columns=features, index=X_p.index)
p_proper = model.predict_proba(X_p)[:, 1]
print("\nB) proper pipeline, winner-POV rows:")
print(f"   p1-win share (=accuracy, p1 is real winner): {(p_proper > 0.5).mean():.4f}")
print(f"   mean={p_proper.mean():.4f} std={p_proper.std():.4f}")

# --- C) proper path + randomized perspective (honest eval) ---
rng = np.random.RandomState(123)
flip = rng.random(len(X_raw)) > 0.5
Xr = X_raw.copy()
for wc in [c for c in features if c.startswith("w_")]:
    lc = "l_" + wc[2:]
    if lc in Xr.columns:
        Xr.loc[flip, [wc, lc]] = X_raw.loc[flip, [lc, wc]].values
for dc in [c for c in features if c.startswith("diff_")]:
    Xr.loc[flip, dc] = -X_raw.loc[flip, dc]
for col in ["rank_diff", "age_diff", "height_diff"]:
    if col in Xr.columns:
        Xr.loc[flip, col] = -X_raw.loc[flip, col]
if "rank_ratio" in Xr.columns:
    Xr.loc[flip, "rank_ratio"] = 1.0 / X_raw.loc[flip, "rank_ratio"]
for col in ["elo_win_prob", "elo_surface_win_prob"]:
    if col in Xr.columns:
        Xr.loc[flip, col] = 1.0 - X_raw.loc[flip, col]
Xr = Xr.fillna(med.reindex(features))
Xr = pd.DataFrame(scaler.transform(Xr), columns=features, index=Xr.index)
p_r = model.predict_proba(Xr)[:, 1]
y_true = (~flip).astype(int)
acc = ((p_r > 0.5).astype(int) == y_true).mean()
from sklearn.metrics import log_loss, roc_auc_score
print("\nC) proper pipeline, randomized perspective (honest):")
print(f"   accuracy: {acc:.4f}  log_loss: {log_loss(y_true, p_r):.4f}  "
      f"roc_auc: {roc_auc_score(y_true, p_r):.4f}")

# --- D) symmetry check: model(p_flipped) should equal 1 - model(p_unflipped) ---
sym_err = np.abs(p_proper[flip] - (1 - p_r[flip])).mean()
print(f"\nD) symmetry error on flipped rows |p_pov - (1-p_flip)|: {sym_err:.4f} (0 = perfectly symmetric)")
