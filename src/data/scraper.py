import os
from dotenv import load_dotenv
load_dotenv()

import json
import urllib.request
import urllib.error
import pandas as pd
import yaml
from datetime import datetime

USER_AGENT = 'Mozilla/5.0'
import dateutil.parser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_config():
    with open(os.path.join(PROJECT_ROOT, "config", "config.yaml"), "r") as f:
        return yaml.safe_load(f)


def fetch_active_tennis_sports(api_key):
    """Discover ALL tennis sport keys (active + inactive) and try them all."""
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={api_key}&all=true"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as response:
            sports = json.loads(response.read().decode('utf-8'))
            # Get ALL tennis keys, not just active ones
            keys = [s['key'] for s in sports if 'tennis' in s.get('group', '').lower()]
            active = [s['key'] for s in sports if s.get('active') and 'tennis' in s.get('group', '').lower()]
            print(f"Discovered {len(keys)} tennis endpoints ({len(active)} active)")
            if active:
                print(f"Active: {active}")
            return keys
    except Exception as e:
        print(f"Error fetching sports list: {e}")
        return ["tennis_atp_french_open", "tennis_atp_wimbledon",
                "tennis_atp_us_open", "tennis_atp_aus_open",
                "tennis_atp_monte_carlo_masters", "tennis_atp_madrid_open",
                "tennis_atp_italian_open", "tennis_atp_indian_wells",
                "tennis_atp_miami_open", "tennis_atp_cincinnati_open",
                "tennis_atp_canadian_open", "tennis_atp_shanghai_masters",
                "tennis_atp_paris_masters"]


def _iter_tennis_events(api_key, regions, markets, bookmakers=None):
    """Yield (sport_key, event) for every tennis event across all endpoints.
    Shared by the live-odds snapshot and the historical CLV logger.

    When `bookmakers` is set, request exactly those books instead of whole
    regions (the-odds-api: 10 bookmakers = 1 region-equivalent in credits)."""
    for sport in fetch_active_tennis_sports(api_key):
        scope = f"bookmakers={bookmakers}" if bookmakers else f"regions={regions}"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds?apiKey={api_key}&{scope}&markets={markets}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as response:
                events = json.loads(response.read().decode('utf-8'))
            for event in events or []:
                yield sport, event
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [!] Rate limit on {sport} — skipping, continuing scan")
                import time as _t
                _t.sleep(2)
            continue
        except Exception:
            continue


def _named_outcome(market, name):
    """Outcome whose name matches, case-insensitively."""
    return next((o for o in market.get('outcomes', [])
                 if o.get('name', '').lower() == name), None)


def _fill_market_prices(row, market, p1, p2):
    """Populate the price columns for one market; False when it is not usable."""
    key = market.get('key')
    outs = {o.get('name'): o for o in market.get('outcomes', [])}
    if key == 'h2h' and p1 in outs and p2 in outs:
        row["price_1"] = outs[p1].get('price')
        row["price_2"] = outs[p2].get('price')
        return True
    if key == 'spreads' and p1 in outs and p2 in outs:
        row["line"] = outs[p1].get('point')
        row["price_1"] = outs[p1].get('price')
        row["price_2"] = outs[p2].get('price')
        return True
    if key == 'totals':
        over = _named_outcome(market, 'over')
        under = _named_outcome(market, 'under')
        if over and under:
            row["over_under_line"] = over.get('point')
            row["over_price"] = over.get('price')
            row["under_price"] = under.get('price')
        return True
    return False


def _event_book_rows(sport, event, snapshot_ts):
    """Flatten ONE event into one row per (bookmaker, market). Captures ALL
    bookmakers (multi-book best-price + soft-book detection) and the snapshot
    timestamp (line movement / CLV). Pre-match info only — no leakage."""
    p1 = event.get('home_team')
    p2 = event.get('away_team')
    commence = event.get('commence_time', '')
    rows = []
    for bk in event.get('bookmakers', []):
        for m in bk.get('markets', []):
            row = {
                "snapshot_ts": snapshot_ts, "commence_time": commence,
                "sport_key": sport, "p1": p1, "p2": p2,
                "bookmaker": bk.get('key'), "market": m.get('key'),
                "line": None, "price_1": None, "price_2": None,
                "over_under_line": None, "over_price": None, "under_price": None,
            }
            if _fill_market_prices(row, m, p1, p2):
                rows.append(row)
    return rows


def snapshot_odds_history(markets=None, regions=None):
    """Append a multi-book, timestamped snapshot of tennis odds to
    data/live/odds_history.csv.

    This is the dataset the alpha roadmap needs (see ALPHA_FINDINGS.md): run on a
    schedule it accumulates line movement for CLV, multi-book best-price, and
    soft-book value. Outcomes are joined later from results.

    Cost note (the-odds-api charges markets x regions per request, per sport):
    pass markets="h2h", regions="eu" (lean mode) for ~6x cheaper CLV snapshots
    that still include Pinnacle + Betfair EU + EU soft books.
    """
    config = load_config()
    api_key = os.getenv("ODDS_API_KEY") or config["data"]["odds_api"].get("api_key", "")
    if not api_key or api_key.startswith("${"):
        print("ERROR: ODDS_API_KEY not set. Export it as an environment variable.")
        return 0
    regions = regions or config["data"]["odds_api"]["regions"]
    markets = markets or "h2h,spreads,totals"
    bookmakers = config["data"]["odds_api"].get("bookmakers", "") or None
    snapshot_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    rows = []
    for sport, event in _iter_tennis_events(api_key, regions, markets, bookmakers=bookmakers):
        try:
            rows.extend(_event_book_rows(sport, event, snapshot_ts))
        except Exception as e:
            print(f"  skip malformed event: {e}")

    out_path = os.path.join(PROJECT_ROOT, 'data', 'live', 'odds_history.csv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty:
        print("No tennis odds returned (off-season or no upcoming matches).")
        return 0
    header = not os.path.exists(out_path)
    df.to_csv(out_path, mode='a', header=header, index=False)
    print(f"Appended {len(df)} book-market rows ({df['p1'].nunique()} matches, "
          f"{df['bookmaker'].nunique()} bookmakers) to data/live/odds_history.csv")
    return len(df)


#: sharpest first — Pinnacle sets the reference line
_PREFERRED_BOOKS = ('pinnacle', 'bet365', 'betfair_ex_eu', 'williamhill', 'betway')


def _get_sport_events(url, sport):
    """Events for one sport key, or [] when the endpoint refuses to answer."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Rate-limited on this sport — skip it, keep scanning the others.
            # Old behaviour (break) killed the whole scan on the first 429.
            print(f"  [!] Rate limit on {sport} — skipping, continuing scan")
            import time as _t
            _t.sleep(2)
        return []
    except Exception:
        return []


def _pick_bookmaker(bookmakers):
    """Highest-priority book present, else whatever came first."""
    for pref in _PREFERRED_BOOKS:
        bk = next((b for b in bookmakers if b['key'].lower() == pref), None)
        if bk:
            return bk
    return bookmakers[0] if bookmakers else None


def _h2h_prices(market, p1_name, p2_name):
    """Head-to-head prices for the two named players; 0.0 for a side nobody quoted."""
    prices = {"o1": 0.0, "o2": 0.0}
    for o in market['outcomes']:
        if o['name'] == p1_name:
            prices['o1'] = o['price']
        elif o['name'] == p2_name:
            prices['o2'] = o['price']
    return prices


def _two_sided_prices(market, first_name, second_name, fold_case=False):
    """(line, first price, second price) for a two-outcome market, or None when
    either side is missing. Spreads match player names as given; totals match
    'over'/'under' case-insensitively."""
    by_name = {}
    for o in market['outcomes']:
        by_name[o['name'].lower() if fold_case else o['name']] = o
    first, second = by_name.get(first_name), by_name.get(second_name)
    if not (first and second):
        return None
    return first['point'], first['price'], second['price']


def _extract_markets(bk, p1_name, p2_name):
    """h2h / spreads / totals prices from one bookmaker block."""
    h2h = {"o1": 0.0, "o2": 0.0}
    spread = {"line": 0.0, "o1": 0.0, "o2": 0.0}
    total = {"line": 0.0, "over": 0.0, "under": 0.0}
    for m in bk.get('markets', []):
        if m['key'] == 'h2h':
            h2h = _h2h_prices(m, p1_name, p2_name)
        elif m['key'] == 'spreads':
            prices = _two_sided_prices(m, p1_name, p2_name)
            if prices:
                spread.update(line=prices[0], o1=prices[1], o2=prices[2])
        elif m['key'] == 'totals':
            prices = _two_sided_prices(m, 'over', 'under', fold_case=True)
            if prices:
                total.update(line=prices[0], over=prices[1], under=prices[2])
    return h2h, spread, total


def _commence_strings(commence_time):
    """(display time, ISO timestamp) — both blank-ish when the field is unparseable."""
    try:
        dt = dateutil.parser.isoparse(commence_time)
    except (ValueError, TypeError):
        return "Upcoming", ""
    return dt.strftime("%H:%M"), dt.strftime("%Y-%m-%dT%H:%M:%S")


def _event_summary(event, sport, sport_label):
    """One scan row for an event, or None when no book quoted a head-to-head price."""
    p1_name = event.get('home_team', 'Unknown P1')
    p2_name = event.get('away_team', 'Unknown P2')
    time_display, commence_iso = _commence_strings(event.get('commence_time', ''))

    bk = _pick_bookmaker(event.get('bookmakers', []))
    if bk is None:
        return None
    h2h, spread, total = _extract_markets(bk, p1_name, p2_name)
    if h2h['o1'] <= 0:
        return None

    return {
        "match": f"[{time_display}] {p1_name} vs {p2_name}",
        "p1": p1_name,
        "p2": p2_name,
        "commence_time": commence_iso,
        "sport_key": sport,
        "sport_title": event.get('sport_title', sport_label),
        "odds_1": h2h['o1'],
        "odds_2": h2h['o2'],
        "spread_line": spread['line'],
        "spread_odds_1": spread['o1'],
        "spread_odds_2": spread['o2'],
        "total_line": total['line'],
        "total_over": total['over'],
        "total_under": total['under'],
        "source": bk['title'],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _sport_matches(sport, api_key, scope, markets):
    """Scan rows for one tennis endpoint. A malformed event is skipped with a
    note, never fatal: one bad payload must not cost the whole scan."""
    url = (f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
           f"?apiKey={api_key}&{scope}&markets={markets}")
    events = _get_sport_events(url, sport)
    if not events:
        return []

    sport_label = sport.replace('tennis_', '').replace('_', ' ').title()
    print(f"  [+] {sport}: {len(events)} events")
    rows = []
    for event in events:
        try:
            row = _event_summary(event, sport, sport_label)
        except Exception as e:
            print(f"Skipping malformed event in {sport}: {e}")
            continue
        if row:
            rows.append(row)
    return rows


def fetch_all_tennis_odds():
    """
    Fetches real pre-match and live odds from The Odds API for all tennis events.
    Tries ALL tennis endpoints (not just 'active') to catch newly posted odds.
    Prioritizes Pinnacle/Bet365 data, with fallbacks to other bookies.
    """
    config = load_config()
    api_key = os.getenv("ODDS_API_KEY") or config["data"]["odds_api"].get("api_key", "")
    if not api_key or api_key.startswith("${"):
        print("ERROR: ODDS_API_KEY not set. Export it as an environment variable.")
        return []
    regions = config["data"]["odds_api"]["regions"]
    markets = config["data"]["odds_api"]["markets"]
    bookmakers = config["data"]["odds_api"].get("bookmakers", "") or None
    scope = f"bookmakers={bookmakers}" if bookmakers else f"regions={regions}"

    all_matches = []
    for sport in fetch_active_tennis_sports(api_key):
        all_matches.extend(_sport_matches(sport, api_key, scope, markets))
    return all_matches

def save_to_csv(matches):
    os.makedirs(os.path.join(PROJECT_ROOT, 'data', 'live'), exist_ok=True)
    df = pd.DataFrame(matches)
    columns = [
        "match", "p1", "p2", "commence_time", "sport_key", "sport_title",
        "odds_1", "odds_2", "spread_line", "spread_odds_1", "spread_odds_2",
        "total_line", "total_over", "total_under", "source", "timestamp",
    ]

    if df.empty:
        print("No active tennis matches with valid odds found.")
        df = pd.DataFrame(columns=columns)
    else:
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df.drop_duplicates(subset=['match'])
        df = df[columns + [col for col in df.columns if col not in columns]]

    csv_path = os.path.join(PROJECT_ROOT, 'data', 'live', 'current_odds.csv')
    df.to_csv(csv_path, index=False)
    print(f"Saved {len(df)} matches to data/live/current_odds.csv")

if __name__ == "__main__":
    import sys
    if "--snapshot" in sys.argv:
        # Multi-book timestamped CLV/soft-book logger (see ALPHA_FINDINGS.md).
        if "--lean" in sys.argv:
            # CLV validation mode: h2h only, eu region (Pinnacle+Betfair+soft) — ~6x cheaper.
            print("Snapshotting odds (LEAN: h2h, eu region)...")
            snapshot_odds_history(markets="h2h", regions="eu")
        else:
            print("Snapshotting odds history (h2h + spreads + totals, all books)...")
            snapshot_odds_history()
    else:
        print("Starting Professional Market Discovery...")
        live_data = fetch_all_tennis_odds()
        save_to_csv(live_data)
        print("Market Discovery Complete.")
