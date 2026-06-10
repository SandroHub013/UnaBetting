"""
Deep Strategy Analysis for ATP Tennis Prediction Model
======================================================
Analyzes backtest realism, profitable probability/odds ranges,
optimal strategy parameters, and risk metrics.

Uses flat staking (EUR 10) as the baseline to avoid Kelly compounding distortion.
"""

import pandas as pd
import numpy as np
import yaml
import joblib
import sys
import warnings
from pathlib import Path
from collections import OrderedDict

warnings.filterwarnings("ignore")

# ============================================================
# CONFIG & DATA LOADING
# ============================================================
PROJECT_ROOT = Path(r"G:\tennis betting")
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

betting_cfg = config["betting"]
test_start_year = config["model"]["test_start_year"]

# Load model, scaler, features
model_dict = joblib.load(PROJECT_ROOT / "models" / "atp_target_rf.pkl")
model = model_dict["model"] if isinstance(model_dict, dict) and "model" in model_dict else model_dict
scaler = joblib.load(PROJECT_ROOT / "models" / "atp_scaler.pkl")
medians = joblib.load(PROJECT_ROOT / "models" / "atp_medians.pkl")
with open(PROJECT_ROOT / "models" / "atp_features.txt") as f:
    feature_names = f.read().strip().split("\n")

# Load features data
df_raw = pd.read_csv(PROJECT_ROOT / "data" / "features" / "atp_features.csv", low_memory=False)
df_raw["tourney_date"] = pd.to_datetime(df_raw["tourney_date"], errors="coerce")

# Filter to test period
df = df_raw[df_raw["tourney_date"].dt.year >= test_start_year].copy()
print(f"[DATA] Total matches in test period (>={test_start_year}): {len(df)}")

# Identify columns
numeric_features = [c for c in feature_names if c in df.columns]
odds_cols = [c for c in df.columns if any(bk in c.upper() for bk in ["B365", "PS", "MAX", "AVG"])]

# Convert odds to numeric
for col in odds_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Drop rows without B365W odds
odds_col = "B365W"
df = df.dropna(subset=[odds_col]).copy()
print(f"[DATA] Matches with {odds_col} odds: {len(df)}")

# ============================================================
# RANDOMIZE PERSPECTIVE (same as backtest.py)
# ============================================================
from src.models.train import _randomize_perspective

np.random.seed(42)
X_to_randomize = df[numeric_features + odds_cols].copy()
y_raw = df["target"].copy()
X_r, y_r = _randomize_perspective(X_to_randomize, y_raw)

# Scale features and predict
X_r_numeric = X_r[numeric_features].fillna(medians)
X_scaled = pd.DataFrame(scaler.transform(X_r_numeric), columns=X_r_numeric.columns, index=X_r_numeric.index)
model_prob = model.predict_proba(X_scaled)[:, 1]

# Build analysis DataFrame
df["model_prob"] = model_prob
df["random_odds"] = X_r[odds_col].values
df["random_odds_L"] = X_r["B365L"].values if "B365L" in X_r.columns else np.nan
df["target_r"] = y_r.values
df["implied_prob"] = 1.0 / df["random_odds"]
df["edge"] = (df["random_odds"] * df["model_prob"]) - 1.0
df["won"] = (df["target_r"] == 1).astype(int)

# Sanity check
print(f"[DATA] After perspective randomization:")
print(f"  model_prob mean: {df['model_prob'].mean():.4f} (should be ~0.50)")
print(f"  target_r mean:   {df['target_r'].mean():.4f} (should be ~0.50)")
print(f"  random_odds mean: {df['random_odds'].mean():.2f}")


# ============================================================
# HELPER: FLAT STAKING SIMULATION
# ============================================================
def flat_stake_analysis(subset, stake=10.0, label=""):
    """Run flat staking analysis on a subset of bets."""
    n = len(subset)
    if n == 0:
        return {"label": label, "n_bets": 0, "win_rate": 0, "profit": 0,
                "roi": 0, "avg_odds": 0, "avg_edge": 0, "avg_prob": 0,
                "max_drawdown": 0, "max_losing_streak": 0, "sharpe": 0,
                "yield_pct": 0}

    won = subset["won"].values
    
    # 1. Slippage (0% to 2% worse odds randomly)
    rng = np.random.RandomState(42)
    slippage = rng.uniform(0, 0.02, size=n)
    odds = subset["random_odds"].values * (1 - slippage)
    
    probs = subset["model_prob"].values
    edges = subset["edge"].values

    # 2. Commission (5% on net winnings)
    commission_rate = 0.05
    pnl = np.where(won == 1, stake * (odds - 1) * (1 - commission_rate), -stake)
    cumulative = np.cumsum(pnl)
    total_profit = cumulative[-1]
    total_staked = n * stake
    roi = total_profit / total_staked * 100

    # Win rate
    win_rate = won.sum() / n * 100

    # Max drawdown
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak
    max_dd = drawdown.min()

    # Longest losing streak
    max_streak = 0
    current_streak = 0
    for w in won:
        if w == 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    # Sharpe-like ratio (daily-ish: per-bet risk-adjusted return)
    if pnl.std() > 0:
        sharpe = (pnl.mean() / pnl.std()) * np.sqrt(252)  # annualized
    else:
        sharpe = 0

    return {
        "label": label,
        "n_bets": n,
        "win_rate": win_rate,
        "profit": total_profit,
        "roi": roi,
        "yield_pct": total_profit / total_staked * 100,
        "avg_odds": odds.mean(),
        "avg_edge": edges.mean() * 100,
        "avg_prob": probs.mean(),
        "max_drawdown": max_dd,
        "max_losing_streak": max_streak,
        "sharpe": sharpe,
    }


def print_table(rows, title=""):
    """Print a formatted ASCII table."""
    if not rows:
        print(f"  (no data for {title})")
        return
    print(f"\n{'=' * 100}")
    print(f"  {title}")
    print(f"{'=' * 100}")
    header = (f"{'Filter':<30} {'Bets':>6} {'Win%':>7} {'Profit':>10} {'ROI%':>7} "
              f"{'AvgOdds':>8} {'AvgEdge%':>9} {'MaxDD':>9} {'LoseStrk':>9} {'Sharpe':>7}")
    print(header)
    print("-" * 100)
    for r in rows:
        line = (f"{r['label']:<30} {r['n_bets']:>6} {r['win_rate']:>6.1f}% "
                f"{r['profit']:>+9.0f}E {r['roi']:>+6.1f}% "
                f"{r['avg_odds']:>8.2f} {r['avg_edge']:>+8.1f}% "
                f"{r['max_drawdown']:>+8.0f}E {r['max_losing_streak']:>9} {r['sharpe']:>7.2f}")
        print(line)
    print("-" * 100)


# ============================================================
# 1. REALISM CHECK: FLAT vs KELLY vs FRACTIONAL KELLY
# ============================================================
print("\n" + "=" * 100)
print("  PART 1: BACKTEST REALISM CHECK -- FLAT vs KELLY STAKING")
print("=" * 100)

min_edge = betting_cfg["min_value_edge"]
min_odds = betting_cfg["min_odds"]
max_odds = betting_cfg["max_odds"]
kelly_frac = betting_cfg["kelly_fraction"]
max_bet_frac = betting_cfg["max_bet_fraction"]
initial_bankroll = betting_cfg["initial_bankroll"]
max_stake_abs = betting_cfg.get("max_stake", 500)

# Value bet mask (same as backtest.py)
value_mask = (
    (df["edge"] >= min_edge) &
    (df["random_odds"] >= min_odds) &
    (df["random_odds"] <= max_odds)
)

# Compute Kelly fraction for each bet
def kelly_f(p, o):
    if pd.isna(o) or o <= 1.0 or pd.isna(p):
        return 0.0
    b = o - 1.0
    f = (b * p - (1 - p)) / b
    return max(0.0, f)

df["kelly_full"] = df.apply(lambda r: kelly_f(r["model_prob"], r["random_odds"]), axis=1)
df["kelly_bet_frac"] = (df["kelly_full"] * kelly_frac).clip(upper=max_bet_frac)
value_mask = value_mask & (df["kelly_bet_frac"] > 0)

value_bets = df[value_mask].copy()

# Add realistic slippage and commission for all simulated bets
np.random.seed(42)
slippage = np.random.uniform(0, 0.02, size=len(value_bets))
value_bets["actual_odds"] = value_bets["random_odds"] * (1 - slippage)
commission_rate = 0.05

print(f"\n  Value bets identified: {len(value_bets)} / {len(df)} matches")

# A) FLAT STAKING (EUR 10)
flat_result = flat_stake_analysis(value_bets, stake=10.0, label="Flat EUR10 (Value)")

# B) KELLY ON GROWING BANKROLL (replicating original backtest)
bankroll = float(initial_bankroll)
kelly_pnl = []
kelly_bankroll_series = []
for _, row in value_bets.iterrows():
    stake = min(bankroll * row["kelly_bet_frac"], max_stake_abs)
    if stake < 1.0:
        continue
    if row["won"] == 1:
        profit = stake * (row["actual_odds"] - 1) * (1 - commission_rate)
    else:
        profit = -stake
    bankroll += profit
    kelly_pnl.append(profit)
    kelly_bankroll_series.append(bankroll)

# Compute staked properly with a second pass
bankroll_sim = float(initial_bankroll)
kelly_stakes = []
kelly_results = []
for _, row in value_bets.iterrows():
    stake = min(bankroll_sim * row["kelly_bet_frac"], max_stake_abs)
    if stake < 1.0:
        continue
    kelly_stakes.append(stake)
    if row["won"] == 1:
        profit = stake * (row["actual_odds"] - 1) * (1 - commission_rate)
    else:
        profit = -stake
    bankroll_sim += profit
    kelly_results.append({"stake": stake, "profit": profit, "bankroll": bankroll_sim})

kelly_df = pd.DataFrame(kelly_results)
kelly_total_staked_proper = kelly_df["stake"].sum()
kelly_total_profit_proper = bankroll_sim - initial_bankroll
kelly_roi = kelly_total_profit_proper / kelly_total_staked_proper * 100 if kelly_total_staked_proper > 0 else 0

# C) FRACTIONAL KELLY ON FIXED BANKROLL (no compounding)
fixed_bank = float(initial_bankroll)
fk_pnl = []
for _, row in value_bets.iterrows():
    stake = min(fixed_bank * row["kelly_bet_frac"], max_stake_abs)  # always based on INITIAL bankroll
    if stake < 1.0:
        continue
    if row["won"] == 1:
        profit = stake * (row["actual_odds"] - 1) * (1 - commission_rate)
    else:
        profit = -stake
    fk_pnl.append(profit)

fk_profit = sum(fk_pnl)
fk_staked = sum(min(fixed_bank * row["kelly_bet_frac"], max_stake_abs)
                for _, row in value_bets.iterrows()
                if min(fixed_bank * row["kelly_bet_frac"], max_stake_abs) >= 1.0)

print(f"\n  --- STAKING COMPARISON (same {len(value_bets)} value bets) ---")
print(f"  {'Method':<35} {'Profit':>12} {'ROI':>8} {'Final Bankroll':>16}")
print(f"  {'-'*75}")
print(f"  {'Flat EUR 10':<35} {flat_result['profit']:>+11.0f}E {flat_result['roi']:>+7.1f}% {initial_bankroll + flat_result['profit']:>15,.0f}E")
if len(kelly_df) > 0:
    print(f"  {'Kelly 25% (growing bankroll)':<35} {kelly_total_profit_proper:>+11,.0f}E {kelly_roi:>+7.1f}% {bankroll_sim:>15,.0f}E")
fk_roi = fk_profit / fk_staked * 100 if fk_staked > 0 else 0
print(f"  {'Kelly 25% (fixed bankroll)':<35} {fk_profit:>+11,.0f}E {fk_roi:>+7.1f}% {initial_bankroll + fk_profit:>15,.0f}E")

print(f"\n  KEY INSIGHT: Flat staking profit of {flat_result['profit']:+.0f}E on {flat_result['n_bets']} bets")
print(f"  shows the TRUE edge. The Kelly compounding amplifies this {'massively' if kelly_total_profit_proper > flat_result['profit'] * 5 else 'significantly'}.")
print(f"  Flat ROI: {flat_result['roi']:+.1f}% is the reliable measure of model quality.")


# ============================================================
# 2. PROBABILITY BIN ANALYSIS (FLAT STAKING)
# ============================================================
print("\n")
prob_bins = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70),
             (0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 1.01)]
prob_rows = []
for lo, hi in prob_bins:
    mask = (df["model_prob"] >= lo) & (df["model_prob"] < hi)
    subset = df[mask]
    label = f"Prob {lo:.2f}-{hi:.2f}"
    prob_rows.append(flat_stake_analysis(subset, stake=10.0, label=label))

print_table(prob_rows, "PART 2: ALL MATCHES BY PROBABILITY BIN (Flat EUR 10)")

# Now same for VALUE bets only
prob_rows_val = []
for lo, hi in prob_bins:
    mask = value_mask & (df["model_prob"] >= lo) & (df["model_prob"] < hi)
    subset = df[mask]
    label = f"Value Prob {lo:.2f}-{hi:.2f}"
    prob_rows_val.append(flat_stake_analysis(subset, stake=10.0, label=label))

print_table(prob_rows_val, "PART 2B: VALUE BETS ONLY BY PROBABILITY BIN (Flat EUR 10)")


# ============================================================
# 3. ODDS RANGE ANALYSIS (FLAT STAKING)
# ============================================================
odds_bins = [(1.01, 1.20), (1.20, 1.50), (1.50, 2.00), (2.00, 3.00), (3.00, 5.00), (5.00, 15.0)]
odds_rows = []
for lo, hi in odds_bins:
    mask = (df["random_odds"] >= lo) & (df["random_odds"] < hi)
    subset = df[mask]
    label = f"Odds {lo:.2f}-{hi:.2f}"
    odds_rows.append(flat_stake_analysis(subset, stake=10.0, label=label))

print_table(odds_rows, "PART 3A: ALL MATCHES BY ODDS RANGE (Flat EUR 10)")

odds_rows_val = []
for lo, hi in odds_bins:
    mask = value_mask & (df["random_odds"] >= lo) & (df["random_odds"] < hi)
    subset = df[mask]
    label = f"Value Odds {lo:.2f}-{hi:.2f}"
    odds_rows_val.append(flat_stake_analysis(subset, stake=10.0, label=label))

print_table(odds_rows_val, "PART 3B: VALUE BETS BY ODDS RANGE (Flat EUR 10)")


# ============================================================
# 4. SURFACE & TOURNAMENT LEVEL ANALYSIS
# ============================================================
surface_rows = []
for surf in ["Hard", "Clay", "Grass"]:
    mask = value_mask & (df["surface"] == surf)
    subset = df[mask]
    surface_rows.append(flat_stake_analysis(subset, stake=10.0, label=f"Value {surf}"))

print_table(surface_rows, "PART 4A: VALUE BETS BY SURFACE (Flat EUR 10)")

level_rows = []
level_labels = {"G": "Grand Slam", "M": "Masters 1000", "500": "ATP 500",
                "250": "ATP 250", "D": "Davis Cup", "F": "Tour Finals", "A": "Other"}
for lvl, lbl in level_labels.items():
    mask = value_mask & (df["tourney_level"] == lvl)
    subset = df[mask]
    level_rows.append(flat_stake_analysis(subset, stake=10.0, label=f"Value {lbl}"))

print_table(level_rows, "PART 4B: VALUE BETS BY TOURNAMENT LEVEL (Flat EUR 10)")


# ============================================================
# 5. STRATEGY COMPARISON -- DIFFERENT FILTERS
# ============================================================
strategies = []

# S1: All bets where model_prob > 0.50
mask_s1 = df["model_prob"] > 0.50
strategies.append(flat_stake_analysis(df[mask_s1], 10.0, "Blind >50%"))

# S2: Threshold >60%
mask_s2 = df["model_prob"] > 0.60
strategies.append(flat_stake_analysis(df[mask_s2], 10.0, "Threshold >60%"))

# S3: Threshold >70%
mask_s3 = df["model_prob"] > 0.70
strategies.append(flat_stake_analysis(df[mask_s3], 10.0, "Threshold >70%"))

# S4: Value bets (original config)
strategies.append(flat_stake_analysis(value_bets, 10.0, "Value (config defaults)"))

# S5: Value + Edge > 5%
mask_s5 = value_mask & (df["edge"] >= 0.05)
strategies.append(flat_stake_analysis(df[mask_s5], 10.0, "Value + Edge>5%"))

# S6: Value + Edge > 10%
mask_s6 = value_mask & (df["edge"] >= 0.10)
strategies.append(flat_stake_analysis(df[mask_s6], 10.0, "Value + Edge>10%"))

# S7: Value + Edge > 15%
mask_s7 = value_mask & (df["edge"] >= 0.15)
strategies.append(flat_stake_analysis(df[mask_s7], 10.0, "Value + Edge>15%"))

# S8: Value + Odds 1.20-3.00
mask_s8 = value_mask & (df["random_odds"] >= 1.20) & (df["random_odds"] <= 3.00)
strategies.append(flat_stake_analysis(df[mask_s8], 10.0, "Value + Odds 1.20-3.00"))

# S9: Value + Odds 1.50-3.00
mask_s9 = value_mask & (df["random_odds"] >= 1.50) & (df["random_odds"] <= 3.00)
strategies.append(flat_stake_analysis(df[mask_s9], 10.0, "Value + Odds 1.50-3.00"))

# S10: Value + Prob 0.55-0.80 + Odds 1.30-4.00
mask_s10 = (value_mask & (df["model_prob"] >= 0.55) & (df["model_prob"] <= 0.80) &
            (df["random_odds"] >= 1.30) & (df["random_odds"] <= 4.00))
strategies.append(flat_stake_analysis(df[mask_s10], 10.0, "Value+Prob55-80+Odds1.3-4"))

# S11: Value + Hard surface only
mask_s11 = value_mask & (df["surface"] == "Hard")
strategies.append(flat_stake_analysis(df[mask_s11], 10.0, "Value + Hard Only"))

# S12: Value + No Davis Cup
mask_s12 = value_mask & (df["tourney_level"] != "D")
strategies.append(flat_stake_analysis(df[mask_s12], 10.0, "Value + No Davis Cup"))

# S13: Value + Grand Slam/Masters only
mask_s13 = value_mask & (df["tourney_level"].isin(["G", "M"]))
strategies.append(flat_stake_analysis(df[mask_s13], 10.0, "Value + GS/Masters"))

# S14: Value + Edge>5% + Odds 1.50-3.00
mask_s14 = value_mask & (df["edge"] >= 0.05) & (df["random_odds"] >= 1.50) & (df["random_odds"] <= 3.00)
strategies.append(flat_stake_analysis(df[mask_s14], 10.0, "Value+E>5%+Odds1.5-3"))

# S15: Value + Edge>10% + Odds 1.20-4.00 + No Davis
mask_s15 = (value_mask & (df["edge"] >= 0.10) & (df["random_odds"] >= 1.20) &
            (df["random_odds"] <= 4.00) & (df["tourney_level"] != "D"))
strategies.append(flat_stake_analysis(df[mask_s15], 10.0, "Value+E>10%+O1.2-4+NoDC"))

print_table(strategies, "PART 5: STRATEGY COMPARISON (Flat EUR 10)")


# ============================================================
# 6. EDGE THRESHOLD SWEEP
# ============================================================
print(f"\n{'=' * 100}")
print(f"  PART 6: EDGE THRESHOLD SWEEP (Value bets, Flat EUR 10)")
print(f"{'=' * 100}")
print(f"  {'MinEdge':>8} {'Bets':>6} {'Win%':>7} {'Profit':>10} {'ROI%':>8} {'AvgOdds':>8} {'Sharpe':>7}")
print(f"  {'-'*60}")
for edge_thresh in [0.00, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20, 0.25, 0.30]:
    mask_e = ((df["edge"] >= edge_thresh) &
              (df["random_odds"] >= min_odds) &
              (df["random_odds"] <= max_odds) &
              (df["kelly_bet_frac"] > 0))
    sub = df[mask_e]
    r = flat_stake_analysis(sub, 10.0, "")
    if r["n_bets"] > 0:
        print(f"  {edge_thresh:>8.2f} {r['n_bets']:>6} {r['win_rate']:>6.1f}% {r['profit']:>+9.0f}E "
              f"{r['roi']:>+7.1f}% {r['avg_odds']:>8.2f} {r['sharpe']:>7.2f}")
print(f"  {'-'*60}")


# ============================================================
# 7. DETAILED RISK ANALYSIS ON BEST STRATEGIES
# ============================================================
print(f"\n{'=' * 100}")
print(f"  PART 7: DETAILED RISK ANALYSIS")
print(f"{'=' * 100}")

# Use the value bets as baseline
for strat_label, strat_mask in [
    ("Value (config defaults)", value_mask),
    ("Value + Edge>5%", value_mask & (df["edge"] >= 0.05)),
    ("Value + Edge>10%", value_mask & (df["edge"] >= 0.10)),
    ("Value + Edge>10% + NoDC", value_mask & (df["edge"] >= 0.10) & (df["tourney_level"] != "D")),
]:
    subset = df[strat_mask].sort_values("tourney_date")
    n = len(subset)
    if n < 10:
        continue

    pnl = np.where(subset["won"].values == 1,
                    10.0 * (subset["random_odds"].values - 1),
                    -10.0)
    cumulative = np.cumsum(pnl)

    # Max drawdown
    peak = np.maximum.accumulate(cumulative)
    dd = cumulative - peak
    max_dd = dd.min()

    # Recovery: how long to recover from max DD
    max_dd_idx = np.argmin(dd)
    recovered = False
    recovery_bets = 0
    for j in range(max_dd_idx + 1, len(cumulative)):
        if cumulative[j] >= peak[max_dd_idx]:
            recovery_bets = j - max_dd_idx
            recovered = True
            break

    # Losing streak
    max_streak = 0
    cs = 0
    for w in subset["won"].values:
        if w == 0:
            cs += 1
            max_streak = max(max_streak, cs)
        else:
            cs = 0

    # Winning streak
    max_win_streak = 0
    cs = 0
    for w in subset["won"].values:
        if w == 1:
            cs += 1
            max_win_streak = max(max_win_streak, cs)
        else:
            cs = 0

    # Monthly P&L
    subset_with_pnl = subset.copy()
    subset_with_pnl["pnl"] = pnl
    monthly = subset_with_pnl.groupby(subset_with_pnl["tourney_date"].dt.to_period("M")).agg(
        bets=("pnl", "count"),
        profit=("pnl", "sum"),
        wins=("won", "sum")
    )
    profitable_months = (monthly["profit"] > 0).sum()
    total_months = len(monthly)

    print(f"\n  --- {strat_label} ({n} bets) ---")
    print(f"  Total Profit (flat EUR 10): {cumulative[-1]:+.0f}E")
    print(f"  ROI: {cumulative[-1] / (n * 10) * 100:+.1f}%")
    print(f"  Win Rate: {subset['won'].mean() * 100:.1f}%")
    print(f"  Max Drawdown: {max_dd:+.0f}E")
    print(f"  Recovery from Max DD: {'%d bets' % recovery_bets if recovered else 'NOT RECOVERED'}")
    print(f"  Max Losing Streak: {max_streak}")
    print(f"  Max Winning Streak: {max_win_streak}")
    print(f"  Profitable Months: {profitable_months}/{total_months}")
    if pnl.std() > 0:
        print(f"  Sharpe (annualized, per-bet): {(pnl.mean() / pnl.std()) * np.sqrt(252):.2f}")
    print(f"  Avg Stake at Risk: EUR 10 (flat)")
    print(f"  Expected Bankroll to withstand 3x MaxDD: EUR {abs(max_dd) * 3:.0f}")

    # Print monthly summary
    if len(monthly) > 0:
        print(f"\n  Monthly Breakdown:")
        print(f"  {'Month':<12} {'Bets':>5} {'Wins':>5} {'Profit':>10}")
        print(f"  {'-'*35}")
        for period, row in monthly.iterrows():
            print(f"  {str(period):<12} {int(row['bets']):>5} {int(row['wins']):>5} {row['profit']:>+9.0f}E")
        print(f"  {'-'*35}")


# ============================================================
# 8. CALIBRATION REALITY CHECK
# ============================================================
print(f"\n{'=' * 100}")
print(f"  PART 8: CALIBRATION REALITY CHECK")
print(f"{'=' * 100}")
print(f"  {'Prob Bin':<18} {'Count':>6} {'Predicted%':>11} {'Actual%':>9} {'Gap':>7} {'Calibrated?':>12}")
print(f"  {'-'*70}")
cal_bins = [(0.30, 0.40), (0.40, 0.50), (0.50, 0.55), (0.55, 0.60), (0.60, 0.65),
            (0.65, 0.70), (0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 1.01)]
for lo, hi in cal_bins:
    mask_c = (df["model_prob"] >= lo) & (df["model_prob"] < hi)
    sub = df[mask_c]
    if len(sub) < 5:
        continue
    pred_avg = sub["model_prob"].mean() * 100
    actual_avg = sub["won"].mean() * 100
    gap = actual_avg - pred_avg
    cal_status = "OK" if abs(gap) < 3 else ("OVER" if gap > 0 else "UNDER")
    print(f"  {f'{lo:.2f}-{hi:.2f}':<18} {len(sub):>6} {pred_avg:>10.1f}% {actual_avg:>8.1f}% {gap:>+6.1f}% {cal_status:>12}")
print(f"  {'-'*70}")

# Overall ECE
bins_data = []
for lo, hi in cal_bins:
    mask_c = (df["model_prob"] >= lo) & (df["model_prob"] < hi)
    sub = df[mask_c]
    if len(sub) < 5:
        continue
    bins_data.append({
        "n": len(sub),
        "pred": sub["model_prob"].mean(),
        "actual": sub["won"].mean()
    })
total_n = sum(b["n"] for b in bins_data)
ece = sum(b["n"] / total_n * abs(b["actual"] - b["pred"]) for b in bins_data)
print(f"\n  Expected Calibration Error (ECE): {ece:.4f}")


# ============================================================
# 9. OVERROUND / MARGIN CHECK
# ============================================================
print(f"\n{'=' * 100}")
print(f"  PART 9: BOOKMAKER MARGIN (OVERROUND) CHECK")
print(f"{'=' * 100}")
# Check using original (non-randomized) B365 odds
orig_b365w = pd.to_numeric(df_raw.loc[df.index, "B365W"], errors="coerce")
orig_b365l = pd.to_numeric(df_raw.loc[df.index, "B365L"], errors="coerce")
both_valid = orig_b365w.notna() & orig_b365l.notna() & (orig_b365w > 1) & (orig_b365l > 1)
if both_valid.sum() > 0:
    overround = (1.0 / orig_b365w[both_valid] + 1.0 / orig_b365l[both_valid])
    print(f"  B365 Overround (mean): {overround.mean():.4f} ({(overround.mean() - 1) * 100:.1f}% margin)")
    print(f"  B365 Overround (median): {overround.median():.4f}")
    print(f"  B365 Overround (range): {overround.min():.4f} - {overround.max():.4f}")
    print(f"  Matches with valid B365W+B365L: {both_valid.sum()}")

    # True (devigged) probability comparison
    print(f"\n  De-vig Analysis (removing margin):")
    true_prob_w = (1.0 / orig_b365w[both_valid]) / overround[both_valid]
    model_prob_subset = df.loc[both_valid[both_valid].index, "model_prob"]
    # This comparison needs perspective-aware logic; skip if too complex
    print(f"  (Note: de-vig comparison requires aligning with randomized perspective)")
else:
    print(f"  Could not compute overround - missing B365L data")


# ============================================================
# 10. FINAL SUMMARY & RECOMMENDATIONS
# ============================================================
print(f"\n{'=' * 100}")
print(f"  PART 10: SUMMARY & RECOMMENDATIONS")
print(f"{'=' * 100}")

# Find best strategy by ROI (with minimum 50 bets)
viable = [s for s in strategies if s["n_bets"] >= 50]
if viable:
    best_roi = max(viable, key=lambda x: x["roi"])
    best_sharpe = max(viable, key=lambda x: x["sharpe"])
    best_profit = max(viable, key=lambda x: x["profit"])

    print(f"\n  BEST BY ROI:    {best_roi['label']:<35} ROI={best_roi['roi']:+.1f}%, {best_roi['n_bets']} bets, Profit={best_roi['profit']:+.0f}E")
    print(f"  BEST BY SHARPE: {best_sharpe['label']:<35} Sharpe={best_sharpe['sharpe']:.2f}, {best_sharpe['n_bets']} bets, ROI={best_sharpe['roi']:+.1f}%")
    print(f"  BEST BY PROFIT: {best_profit['label']:<35} Profit={best_profit['profit']:+.0f}E, {best_profit['n_bets']} bets, ROI={best_profit['roi']:+.1f}%")

print(f"\n  FLAT STAKING BASELINE (Value Config Defaults):")
print(f"    Bets: {flat_result['n_bets']}")
print(f"    Profit: {flat_result['profit']:+.0f}E on {flat_result['n_bets'] * 10:,}E staked")
print(f"    ROI: {flat_result['roi']:+.1f}%")
print(f"    Win Rate: {flat_result['win_rate']:.1f}%")
print(f"    Max Drawdown: {flat_result['max_drawdown']:+.0f}E")
print(f"    Longest Losing Streak: {flat_result['max_losing_streak']}")

print(f"\n  KELLY COMPOUNDING EFFECT:")
print(f"    Kelly 25% (growing bankroll) profit: {kelly_total_profit_proper:+,.0f}E")
print(f"    Flat EUR 10 profit:                  {flat_result['profit']:+,.0f}E")
if flat_result['profit'] != 0:
    print(f"    Inflation factor:                    {kelly_total_profit_proper / flat_result['profit']:.1f}x")

print(f"\n  The Kelly compounding result ({kelly_total_profit_proper:+,.0f}E) is mathematically valid")
print(f"  under perfect execution, but UNREALISTIC in practice because:")
print(f"  1. Bookmaker limits: stakes would be restricted long before reaching hundreds of EUR")
print(f"  2. Odds movement: large bets move lines, reducing edge")
print(f"  3. Model confidence: out-of-sample accuracy may degrade over time")
print(f"  4. Execution: real-world slippage, account restrictions, timing issues")
print(f"\n  REALISTIC EXPECTATION (flat EUR 10): {flat_result['profit']:+.0f}E profit over the test period")
print(f"  Scale appropriately: EUR 100 flat -> {flat_result['profit'] * 10:+,.0f}E profit")

print(f"\n{'=' * 100}")
print(f"  ANALYSIS COMPLETE")
print(f"{'=' * 100}")
