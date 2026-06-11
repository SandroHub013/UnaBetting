"""One-off: add the has_odds column to the existing atp_features.csv without
re-running the full (slow) feature build. Mirrors the logic added to
build_features._add_implied_probabilities."""
from pathlib import Path

import numpy as np
import pandas as pd

path = Path("G:/tennis betting/data/features/atp_features.csv")
df = pd.read_csv(path, low_memory=False)

if "has_odds" in df.columns:
    print("has_odds already present, nothing to do")
else:
    def num(col):
        return pd.to_numeric(df.get(col, pd.Series(np.nan, index=df.index)), errors="coerce")

    w_odds = num("B365W").fillna(num("PSW")).fillna(num("AvgW"))
    l_odds = num("B365L").fillna(num("PSL")).fillna(num("AvgL"))
    df["has_odds"] = (w_odds.notna() & l_odds.notna() & (w_odds > 1.0) & (l_odds > 1.0)).astype(float)
    df.to_csv(path, index=False)
    print(f"has_odds added: {df['has_odds'].mean():.1%} of {len(df)} rows have real odds")
    by_year = df.assign(year=pd.to_datetime(df["tourney_date"], errors="coerce").dt.year) \
                .groupby("year")["has_odds"].mean()
    print(by_year.loc[by_year.index >= 2020].round(3).to_string())
