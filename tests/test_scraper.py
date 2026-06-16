"""
Tests for the odds-history flattening (multi-book CLV/soft-book logger).
Pure parsing — no network. See ALPHA_FINDINGS.md for why this dataset matters.
"""
import pandas as pd

from src.data import scraper
from src.data.scraper import _event_book_rows


def _event():
    return {
        "home_team": "Alcaraz",
        "away_team": "Sinner",
        "commence_time": "2026-05-25T13:00:00Z",
        "bookmakers": [
            {"key": "pinnacle", "title": "Pinnacle", "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Alcaraz", "price": 1.8},
                    {"name": "Sinner", "price": 2.05}]},
                {"key": "spreads", "outcomes": [
                    {"name": "Alcaraz", "price": 1.9, "point": -2.5},
                    {"name": "Sinner", "price": 1.9, "point": 2.5}]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "price": 1.95, "point": 22.5},
                    {"name": "Under", "price": 1.85, "point": 22.5}]},
            ]},
            {"key": "williamhill", "title": "William Hill", "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Alcaraz", "price": 1.75},
                    {"name": "Sinner", "price": 2.10}]},
            ]},
        ],
    }


def test_captures_all_bookmakers_and_markets():
    rows = _event_book_rows("tennis_atp_x", _event(), "2026-05-24T10:00:00")
    # pinnacle: h2h+spreads+totals (3) + williamhill: h2h (1) = 4 rows
    assert len(rows) == 4
    books = {r["bookmaker"] for r in rows}
    assert books == {"pinnacle", "williamhill"}


def test_h2h_prices_and_snapshot_ts():
    rows = _event_book_rows("tennis_atp_x", _event(), "2026-05-24T10:00:00")
    h2h = next(r for r in rows if r["bookmaker"] == "pinnacle" and r["market"] == "h2h")
    assert h2h["price_1"] == 1.8 and h2h["price_2"] == 2.05
    assert h2h["snapshot_ts"] == "2026-05-24T10:00:00"
    assert h2h["p1"] == "Alcaraz" and h2h["p2"] == "Sinner"


def test_spread_and_total_lines_captured():
    rows = _event_book_rows("tennis_atp_x", _event(), "t")
    sp = next(r for r in rows if r["market"] == "spreads")
    assert sp["line"] == -2.5 and sp["price_1"] == 1.9
    tot = next(r for r in rows if r["market"] == "totals")
    assert tot["over_under_line"] == 22.5 and tot["over_price"] == 1.95 and tot["under_price"] == 1.85


def test_empty_bookmakers_yields_no_rows():
    ev = {"home_team": "A", "away_team": "B", "commence_time": "", "bookmakers": []}
    assert _event_book_rows("s", ev, "t") == []


def test_empty_current_odds_csv_keeps_live_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "PROJECT_ROOT", str(tmp_path))

    scraper.save_to_csv([])

    df = pd.read_csv(tmp_path / "data" / "live" / "current_odds.csv")
    assert {"match", "p1", "p2", "commence_time", "sport_key", "sport_title"} <= set(df.columns)
