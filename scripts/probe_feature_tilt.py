"""Per-feature winner-tilt probe: which features 'know' the winner too well?"""
import pandas as pd
import numpy as np

df = pd.read_csv("G:/tennis betting/data/features/atp_features.csv", low_memory=False)
df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
df["year"] = df["tourney_date"].dt.year
print("rows:", len(df), "years:", int(df["year"].min()), "-", int(df["year"].max()))

odds_cols = [c for c in df.columns if "B365" in c or "implied" in c
             or c in ("AvgW", "AvgL", "MaxW", "MaxL", "PSW", "PSL")]
print("odds cols:", odds_cols)

print("\nper-year tilt accuracy (share of rows where w_ side > l_ side):")
for y in range(2021, 2027):
    d = df[df["year"] == y].dropna(subset=["w_implied_prob", "l_implied_prob"])
    if len(d) == 0:
        continue
    fav = (d["w_implied_prob"] > d["l_implied_prob"]).mean()
    elo = (d["elo_win_prob"] > 0.5).mean() if "elo_win_prob" in d else np.nan
    selo = (d["elo_surface_win_prob"] > 0.5).mean() if "elo_surface_win_prob" in d else np.nan
    print(f"  {y}: n={len(d):5d} mkt_fav={fav:.3f} elo={elo:.3f} surf_elo={selo:.3f}")

# raw B365 sanity if present (columns contain strings -> coerce)
if "B365W" in df.columns:
    bw = pd.to_numeric(df["B365W"], errors="coerce")
    bl = pd.to_numeric(df["B365L"], errors="coerce")
    m = bw.notna() & bl.notna()
    n_str = df["B365W"].notna().sum() - bw.notna().sum()
    print(f"\nB365W non-numeric entries: {n_str}")
    print(f"raw B365 favorite acc (B365W<B365L): {(bw[m] < bl[m]).mean():.3f} n={int(m.sum())}")
    # is w_implied_prob consistent with raw B365 no-vig?
    sub = df[m].copy()
    pw_novig = (1 / bw[m]) / (1 / bw[m] + 1 / bl[m])
    corr = np.corrcoef(pw_novig, sub["w_implied_prob"].astype(float))[0, 1]
    print(f"corr(no-vig B365 prob, w_implied_prob): {corr:.3f}")
    inv_corr = np.corrcoef(1 - pw_novig, sub["w_implied_prob"].astype(float))[0, 1]
    print(f"corr with INVERTED prob: {inv_corr:.3f}")

pairs = [
    ("w_clutch_bp_saved_pct", "l_clutch_bp_saved_pct"),
    ("w_vs_server_elo", "l_vs_server_elo"),
    ("w_vs_returner_elo", "l_vs_returner_elo"),
    ("w_pressure_ratio", "l_pressure_ratio"),
    ("w_defending_pts", "l_defending_pts"),
    ("w_form_ewm", "l_form_ewm"),
    ("w_elo", "l_elo"),
    ("w_surface_elo", "l_surface_elo"),
    ("w_win_rate_surface", "l_win_rate_surface"),
    ("w_h2h_win_rate", "l_h2h_win_rate"),
    ("w_return_pts_win_pct_50", "l_return_pts_win_pct_50"),
    ("w_bp_convert_pct_50", "l_bp_convert_pct_50"),
    ("w_break_rate_50", "l_break_rate_50"),
    ("w_minutes_last_14d", "l_minutes_last_14d"),
]
print("\nfeature-pair tilt (w > l share) — honest features ~0.55-0.66, >0.75 = leak suspect:")
for wc, lc in pairs:
    if wc in df.columns and lc in df.columns:
        d = df.dropna(subset=[wc, lc])
        d = d[d[wc] != d[lc]]
        if len(d):
            print(f"  {wc:28s} {(d[wc] > d[lc]).mean():.3f}  n={len(d)}")

for c in ["cpi", "wind_speed", "diff_elo_x_form", "diff_age_x_fatigue", "abs_elo_prob_diff"]:
    if c in df.columns:
        d = df.dropna(subset=[c])
        print(f"  {c:28s} nan%={df[c].isna().mean()*100:5.1f}  mean={d[c].mean():.4f}")

# diff_ features: positive mean = winner-tilt encoded pre-flip (expected in raw CSV)
print("\ndiff_ feature sign tilt (share > 0):")
for c in [c for c in df.columns if c.startswith("diff_")]:
    d = df[df[c].notna() & (df[c] != 0)]
    if len(d):
        print(f"  {c:28s} {(d[c] > 0).mean():.3f}  n={len(d)}")
