"""Which ADM-licensed book (present in our odds feed) prices tennis best?

Uses data/live/odds_history.csv (h2h snapshots). Metrics per book:
- mean overround (1/p1 + 1/p2 - 1): lower = better prices structurally
- best-price share: how often the book has the top price on a side, among
  the ADM-legal set only (excluding the exchange, which has no margin)
- mean price ratio vs Pinnacle (same snapshot/match/side): >1 = beats sharp
"""
import pandas as pd

# 2026-06-10: ridotto al set operativo del progetto (sharp + venue ADM scelti)
ADM = ["williamhill", "sport888", "marathonbet", "betfair_ex_eu", "betfair_ex_uk"]
EXCHANGES = {"betfair_ex_eu", "betfair_ex_uk"}

df = pd.read_csv(r"G:\tennis betting\data\live\odds_history.csv")
h2h = df[(df["market"] == "h2h") & df["price_1"].notna() & df["price_2"].notna()].copy()
h2h["match_key"] = h2h["snapshot_ts"] + "|" + h2h["p1"] + "|" + h2h["p2"]

print(f"h2h rows: {len(h2h)}, snapshots/match combos: {h2h['match_key'].nunique()}\n")

# --- overround per book ---
h2h["overround"] = 1 / h2h["price_1"] + 1 / h2h["price_2"] - 1
agg = (h2h[h2h["bookmaker"].isin(ADM + ["pinnacle"])]
       .groupby("bookmaker")["overround"].agg(["mean", "count"]))
print("OVERROUND medio (margine; più basso = quote migliori):")
for b, row in agg.sort_values("mean").iterrows():
    tag = " (exchange: prezzi senza margine, paghi commissione ~4.5% su .it)" if b in EXCHANGES else ""
    print(f"  {b:16s} {row['mean']*100:6.2f}%   n={int(row['count']):5d}{tag}")

# --- best price share among ADM bookmakers (no exchanges) ---
adm_books = [b for b in ADM if b not in EXCHANGES]
sub = h2h[h2h["bookmaker"].isin(adm_books)].copy()
wins = {b: 0 for b in adm_books}
tot = 0
for _, g in sub.groupby("match_key"):
    if g["bookmaker"].nunique() < 3:
        continue
    for side in ["price_1", "price_2"]:
        best = g[side].max()
        tot += 1
        for b in g.loc[g[side] == best, "bookmaker"].unique():
            wins[b] += 1
print(f"\nMIGLIOR QUOTA tra i book ADM (su {tot} lati, match con >=3 book; pari merito conta per tutti):")
cov = sub.groupby("bookmaker")["match_key"].nunique()
for b, w in sorted(wins.items(), key=lambda x: -x[1]):
    print(f"  {b:16s} {w/tot*100:5.1f}%   (copertura: {cov.get(b, 0)} match)")

# --- ratio vs pinnacle ---
pin = h2h[h2h["bookmaker"] == "pinnacle"][["match_key", "price_1", "price_2"]] \
        .rename(columns={"price_1": "pin1", "price_2": "pin2"})
merged = sub.merge(pin, on="match_key", how="inner")
merged["r1"] = merged["price_1"] / merged["pin1"]
merged["r2"] = merged["price_2"] / merged["pin2"]
ratio = merged.groupby("bookmaker")[["r1", "r2"]].mean()
ratio["mean_ratio"] = (ratio["r1"] + ratio["r2"]) / 2
print("\nPREZZO MEDIO vs PINNACLE (1.00 = pari allo sharp; piu' alto = piu' generoso):")
for b, row in ratio.sort_values("mean_ratio", ascending=False).iterrows():
    print(f"  {b:16s} {row['mean_ratio']:.4f}")
