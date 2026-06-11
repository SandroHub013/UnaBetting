"""
Value-bet signal engine + Closing Line Value (CLV) tracker.

Honest premise (see docs/ALPHA_FINDINGS.md): our ML model does NOT beat the market.
The reliable "prediction" is the SHARP no-vig consensus (Pinnacle + exchanges).
A value bet is a SOFT book offering a price higher than that fair line — a single
+EV wager (not arbitrage).

The integrity guarantee is CLV: a signal is only "serious" if the price we took
beats the closing (sharp) line over time. Win/loss on single bets is noise; CLV
is the real, provable edge metric. Sell nothing until CLV is positive and stable.

Data source: data/live/odds_history.csv (multi-book timestamped snapshots from
src/data/scraper.py --snapshot).
"""
import os
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Books with a track record of stale / palpable-error / will-be-voided lines.
LOOSE_BOOKS = {"onexbet"}

# 2026-06-10: the ONLY books considered anywhere in the project —
# Pinnacle (sharp reference) + the ADM-legal execution venues in Italy.
# Everything else in old odds_history rows is ignored at read time.
ALLOWED_BOOKS = {"pinnacle", "williamhill", "sport888", "marathonbet",
                 "betfair_ex_eu", "betfair_ex_uk"}


def filter_allowed(df):
    """Restrict any odds dataframe to the allowed bookmaker set."""
    if "bookmaker" in df.columns:
        return df[df["bookmaker"].isin(ALLOWED_BOOKS)]
    return df

# Commission on NET winnings (betting exchanges). Reduces effective odds.
COMMISSION = {
    "betfair_ex_uk": 0.05, "betfair_ex_eu": 0.05, "betfair_ex_au": 0.05,
    "matchbook": 0.02, "smarkets": 0.02,
}


def effective_odds(decimal_odds, bookmaker):
    """Odds after the book's commission on winnings (exchanges)."""
    c = COMMISSION.get(bookmaker, 0.0)
    return 1.0 + (decimal_odds - 1.0) * (1.0 - c)

# Sharpest books / exchanges — define the "fair" line. NOT signal sources.
SHARP_BOOKS = {"pinnacle", "betfair_ex_eu", "betfair_ex_uk", "betfair_ex_au",
               "smarkets", "matchbook"}


def sharp_consensus(h2h_df):
    """Per match, the no-vig fair win probabilities from sharp books (averaged).

    Uses commission-adjusted odds for exchanges. Returns dict keyed by
    (p1, p2, commence_time) -> (fair_p1, fair_p2, n_sharp).
    """
    df = h2h_df[h2h_df["market"] == "h2h"] if "market" in h2h_df.columns else h2h_df
    df = df[df["bookmaker"].isin(SHARP_BOOKS)].dropna(subset=["price_1", "price_2"])
    df = df[(df["price_1"] > 1) & (df["price_2"] > 1)]
    out = {}
    for (p1, p2, ct), g in df.groupby(["p1", "p2", "commence_time"]):
        fairs = []
        for _, r in g.iterrows():
            e1 = effective_odds(r["price_1"], r["bookmaker"])
            e2 = effective_odds(r["price_2"], r["bookmaker"])
            ip1, ip2 = 1.0 / e1, 1.0 / e2
            fairs.append(ip1 / (ip1 + ip2))  # no-vig P(p1)
        fp1 = sum(fairs) / len(fairs)
        out[(p1, p2, ct)] = (fp1, 1.0 - fp1, len(g))
    return out


def find_value_bets(h2h_df, min_edge=0.03, max_edge=0.20, exclude=LOOSE_BOOKS):
    """Soft-book prices that beat the sharp no-vig consensus.

    edge = offered_odds * sharp_fair_prob - 1. Flags min_edge <= edge <= max_edge.
    max_edge caps obvious stale/error lines (huge "edges" are traps, not value).
    Returns the best soft price per (match, side), with the implied edge.
    """
    df = h2h_df[h2h_df["market"] == "h2h"] if "market" in h2h_df.columns else h2h_df
    df = filter_allowed(df)
    df = df.dropna(subset=["price_1", "price_2"])
    df = df[(df["price_1"] > 1) & (df["price_2"] > 1)]
    fair = sharp_consensus(df)

    soft = df[~df["bookmaker"].isin(SHARP_BOOKS | set(exclude))]
    best = {}  # (match, side) -> row dict, keep highest edge
    for _, r in soft.iterrows():
        key = (r["p1"], r["p2"], r["commence_time"])
        if key not in fair:
            continue
        fp1, fp2, nsharp = fair[key]
        for side, odds, fp in ((1, r["price_1"], fp1), (2, r["price_2"], fp2)):
            edge = odds * fp - 1.0
            if min_edge <= edge <= max_edge:
                k = (r["p1"], r["p2"], r["commence_time"], side)
                if k not in best or edge > best[k]["edge"]:
                    best[k] = {
                        "match": f"{r['p1']} v {r['p2']}",
                        "commence_time": r["commence_time"],
                        "side": "p1" if side == 1 else "p2",
                        "player": r["p1"] if side == 1 else r["p2"],
                        "book": r["bookmaker"], "odds": odds,
                        "sharp_fair_prob": round(fp, 4),
                        "fair_odds": round(1.0 / fp, 2),
                        "edge": round(edge, 4), "n_sharp": nsharp,
                    }
    cols = ["match", "player", "side", "book", "odds", "fair_odds",
            "sharp_fair_prob", "edge", "n_sharp", "commence_time"]
    res = pd.DataFrame(list(best.values()), columns=cols)
    return res.sort_values("edge", ascending=False).reset_index(drop=True)


def compute_clv(signals_df, odds_history_df):
    """Closing Line Value for each logged signal.

    For each signal (match, side, taken odds), find the LAST snapshot before
    commence_time and the sharp fair odds for that side at the close. Positive
    CLV (taken odds > closing fair odds) is the provable edge.

    Needs multiple snapshots over time — returns NaN CLV where no later/closing
    snapshot exists yet.
    """
    h = odds_history_df[odds_history_df["market"] == "h2h"].copy()
    h = filter_allowed(h)
    h = h.dropna(subset=["price_1", "price_2"])
    rows = []
    for _, s in signals_df.iterrows():
        m = h[(h["p1"] + " v " + h["p2"] == s["match"]) &
              (h["commence_time"] == s["commence_time"])]
        # closing = latest snapshot strictly at/after the signal, before kickoff
        closing = m[m["snapshot_ts"] <= s["commence_time"]]
        clv = float("nan")
        close_fair_odds = float("nan")
        if len(closing):
            last_ts = closing["snapshot_ts"].max()
            fair = sharp_consensus(closing[closing["snapshot_ts"] == last_ts])
            key = next(iter(fair), None)
            if key:
                fp1, fp2, _ = fair[key]
                fp = fp1 if s["side"] == "p1" else fp2
                if fp > 0:
                    close_fair_odds = 1.0 / fp
                    clv = s["odds"] / close_fair_odds - 1.0
        r = s.to_dict()
        r["closing_fair_odds"] = round(close_fair_odds, 3) if close_fair_odds == close_fair_odds else None
        r["clv"] = round(clv, 4) if clv == clv else None
        rows.append(r)
    return pd.DataFrame(rows)


def log_signals(value_bets, path=None):
    """Append today's value-bet signals to the signals log (for later CLV)."""
    path = path or os.path.join(PROJECT_ROOT, "data", "live", "signals_log.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if value_bets.empty:
        return 0
    vb = value_bets.copy()
    vb["logged_ts"] = pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S")
    header = not os.path.exists(path)
    vb.to_csv(path, mode="a", header=header, index=False)
    return len(vb)


def scan_and_log(snapshot_path=None, min_edge=0.03, do_log=True):
    snapshot_path = snapshot_path or os.path.join(PROJECT_ROOT, "data", "live", "odds_history.csv")
    if not os.path.exists(snapshot_path):
        print(f"No snapshot at {snapshot_path}. Run: python -m src.data.scraper --snapshot")
        return pd.DataFrame()
    h = pd.read_csv(snapshot_path)
    if "snapshot_ts" in h.columns and h["snapshot_ts"].notna().any():
        h = h[h["snapshot_ts"] == h["snapshot_ts"].max()]
    vb = find_value_bets(h, min_edge=min_edge)
    if do_log and len(vb):
        n = log_signals(vb)
        print(f"Logged {n} value-bet signals to data/live/signals_log.csv (for CLV).")
    return vb


if __name__ == "__main__":
    vb = scan_and_log(do_log=False)
    if len(vb):
        print(f"{len(vb)} value bets vs sharp consensus (soft books, edge 3-20%):")
        print(vb.to_string(index=False))
    else:
        print("No value bets in the latest snapshot.")
