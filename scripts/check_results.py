"""Daily reality check: did our live-scanned predictions actually win?

Reads recent decisions from betanalytix.db, fetches final results from the
Sofascore public API, matches players by name, and appends the comparison to
reports/results_feedback.csv. Prints an honest rolling accuracy summary.

Run: python scripts/check_results.py [--days 3]
"""
import argparse
import csv
import json
import re
import sqlite3
import unicodedata
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "betanalytix.db"
OUT = ROOT / "reports" / "results_feedback.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def norm(name):
    """lowercase, strip accents, keep letters/spaces."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def last_name(name):
    parts = norm(name).split()
    return parts[-1] if parts else ""


def fetch_day(date_str):
    """Sofascore blocks python TLS fingerprints (403) but allows curl.exe."""
    import subprocess
    url = f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date_str}"
    r = subprocess.run(
        ["curl.exe", "-s", "--compressed", "-m", "25", url,
         "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
         "-H", "Accept: */*", "-H", "Referer: https://www.sofascore.com/"],
        capture_output=True, timeout=40)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl exit {r.returncode}")
    return json.loads(r.stdout).get("events", [])


def _recent_decisions(days):
    """Logged decisions from the last ``days``, oldest first."""
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, timestamp, match_str, p1_name, p2_name, ml_prob_1, ml_prob_2, "
        "news_adj_prob_1, news_adj_prob_2, edge, value_side FROM decisions "
        "WHERE timestamp >= ? ORDER BY timestamp", (since,))]
    conn.close()
    return rows


def _already_checked():
    """Decision ids already present in the feedback CSV, so reruns stay idempotent."""
    if not OUT.exists():
        return set()
    with open(OUT, newline="", encoding="utf-8") as f:
        return {row["decision_id"] for row in csv.DictReader(f)}


def _finished_winners(decisions):
    """{frozenset(last names): winning last name} for every finished sofascore match."""
    dates = set()
    for d in decisions:
        day = datetime.fromisoformat(d["timestamp"]).date()
        dates.add(str(day))
        dates.add(str(day + timedelta(days=1)))  # late finishes roll over midnight

    events = []
    for ds in sorted(dates):
        try:
            evs = fetch_day(ds)
            events.extend(evs)
            print(f"  sofascore {ds}: {len(evs)} eventi")
        except Exception as e:
            print(f"  sofascore {ds}: errore {e}")

    finished = {}
    for ev in events:
        if ev.get("status", {}).get("type") != "finished":
            continue
        h = last_name(ev.get("homeTeam", {}).get("name", ""))
        a = last_name(ev.get("awayTeam", {}).get("name", ""))
        w = ev.get("winnerCode")  # sofascore: home is 1, away is 2
        if h and a and w in (1, 2):
            finished[frozenset((h, a))] = (h if w == 1 else a)
    return finished


def _score_decision(d, winner_ln, l1):
    """One feedback row for a decision whose match has a known winner."""
    pick = d["p1_name"] if (d["ml_prob_1"] or 0) >= (d["ml_prob_2"] or 0) else d["p2_name"]
    pick_news = d["p1_name"] if (d["news_adj_prob_1"] or 0) >= (d["news_adj_prob_2"] or 0) else d["p2_name"]
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "decision_id": d["id"], "scanned_at": d["timestamp"],
        "match": d["match_str"], "ml_pick": pick, "news_pick": pick_news,
        "actual_winner": d["p1_name"] if winner_ln == l1 else d["p2_name"],
        "ml_correct": int(last_name(pick) == winner_ln),
        "news_correct": int(last_name(pick_news) == winner_ln),
    }


def _score_decisions(decisions, finished, seen):
    rows = []
    for d in decisions:
        if d["id"] in seen:
            continue
        l1, l2 = last_name(d["p1_name"]), last_name(d["p2_name"])
        winner_ln = finished.get(frozenset((l1, l2)))
        if winner_ln:
            rows.append(_score_decision(d, winner_ln, l1))
    return rows


def _append_rows(rows):
    OUT.parent.mkdir(exist_ok=True)
    new_file = not OUT.exists()
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new_file:
            w.writeheader()
        w.writerows(rows)


def _print_summary(rows):
    checked = len(rows)
    correct = sum(r["ml_correct"] for r in rows)
    print(f"\nverificati ora: {checked} match — modello corretto {correct}/{checked}"
          + (f" ({correct/checked*100:.0f}%)" if checked else ""))
    if not OUT.exists():
        return
    with open(OUT, newline="", encoding="utf-8") as f:
        allr = list(csv.DictReader(f))
    tot = len(allr)
    acc = sum(int(r["ml_correct"]) for r in allr) / tot * 100 if tot else 0
    acc_news = sum(int(r.get("news_correct", 0)) for r in allr) / tot * 100 if tot else 0
    print(f"storico feedback: {tot} match — ML {acc:.1f}% | ML+news {acc_news:.1f}%"
          f" (riferimento test offline: 66.3%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()

    if not DB.exists():
        print("no betanalytix.db")
        return
    decisions = _recent_decisions(args.days)
    if not decisions:
        print("no recent decisions to check")
        return

    rows = _score_decisions(decisions, _finished_winners(decisions), _already_checked())
    if rows:
        _append_rows(rows)
    _print_summary(rows)


if __name__ == "__main__":
    main()
