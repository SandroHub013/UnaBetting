"""Verify backtest claims: is the 85% win rate real or an artifact?

Checks, on the 2025+ period used by src/models/backtest.py:
1. Model accuracy on winner-POV (unflipped) rows  -> should be ~test acc (66-67%) if no POV leak
2. Model accuracy on perspective-randomized rows  -> honest accuracy
3. Replicates the backtest bet-selection logic    -> win rate decomposition
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path("G:/tennis betting")

df = pd.read_csv(ROOT / "data/features/atp_features.csv", low_memory=False)
df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
test_df = df[df["tourney_date"].dt.year >= 2025].copy().sort_values("tourney_date")
test_df = test_df.dropna(subset=["w_implied_prob", "l_implied_prob"])
print(f"matches 2025+ with odds: {len(test_df)}")

model_data = joblib.load(ROOT / "models/atp_target_xgboost.pkl")
print(f"pkl keys: {list(model_data.keys()) if isinstance(model_data, dict) else type(model_data)}")
model = model_data["model"]
features = model_data["feature_cols"]
print(f"n features: {len(features)}")

missing = [f for f in features if f not in test_df.columns]
if missing:
    print(f"MISSING FEATURES IN CSV: {missing}")

X = test_df[features].copy()
nan_rate = X.isna().mean().sort_values(ascending=False)
print("\ntop-10 NaN rate features (2025+):")
print(nan_rate.head(10).to_string())

# --- exactly like backtest.py (test-median imputation) ---
X_bt = X.fillna(X.median())
probs = model.predict_proba(X_bt)
p_w = probs[:, 1]

acc_winner_pov = float((p_w > 0.5).mean())
print(f"\n[1] winner-POV accuracy (p1>0.5 share): {acc_winner_pov:.4f}")
print(f"    mean p_w_model: {p_w.mean():.4f}")

# --- honest: randomize perspective like training does ---
rng = np.random.RandomState(123)
flip = rng.random(len(X)) > 0.5
Xr = X.copy()
for wc in [c for c in features if c.startswith("w_")]:
    lc = "l_" + wc[2:]
    if lc in Xr.columns:
        Xr.loc[flip, [wc, lc]] = X.loc[flip, [lc, wc]].values
for dc in [c for c in features if c.startswith("diff_")]:
    Xr.loc[flip, dc] = -X.loc[flip, dc]
for col in ["rank_diff", "age_diff", "height_diff"]:
    if col in Xr.columns:
        Xr.loc[flip, col] = -X.loc[flip, col]
if "rank_ratio" in Xr.columns:
    Xr.loc[flip, "rank_ratio"] = 1.0 / X.loc[flip, "rank_ratio"]
for col in ["elo_win_prob", "elo_surface_win_prob"]:
    if col in Xr.columns:
        Xr.loc[flip, col] = 1.0 - X.loc[flip, col]
Xr = Xr.fillna(Xr.median())
pr = model.predict_proba(Xr)[:, 1]
y_true = (~flip).astype(int)  # p1 wins iff row NOT flipped
pred = (pr > 0.5).astype(int)
acc_honest = float((pred == y_true).mean())
print(f"[2] randomized-perspective accuracy: {acc_honest:.4f}")

# --- replicate backtest bet logic ---
test_df["p_w_model"] = p_w
test_df["p_l_model"] = probs[:, 0]
edge_w = test_df["p_w_model"] - test_df["w_implied_prob"]
edge_l = test_df["p_l_model"] - test_df["l_implied_prob"]
MIN_EDGE = 0.03
bet_w = (edge_w > MIN_EDGE) & (edge_w > edge_l)
bet_l = (edge_l > MIN_EDGE) & (edge_l > edge_w) & ~bet_w
n_w, n_l = int(bet_w.sum()), int(bet_l.sum())
print(f"\n[3] backtest bet decomposition:")
print(f"    bets on p1 (auto-WIN):  {n_w}")
print(f"    bets on p2 (auto-LOSE): {n_l}")
if n_w + n_l:
    print(f"    'win rate': {n_w / (n_w + n_l) * 100:.1f}%")

# vig check: implied probs sum
s = test_df["w_implied_prob"] + test_df["l_implied_prob"]
print(f"\n[4] implied prob sum (vig check): mean={s.mean():.4f} min={s.min():.4f} max={s.max():.4f}")

# market accuracy baseline
mkt_acc = float((test_df["w_implied_prob"] > test_df["l_implied_prob"]).mean())
print(f"[5] market favorite accuracy 2025+: {mkt_acc:.4f}")
