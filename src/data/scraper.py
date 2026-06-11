import os
from dotenv import load_dotenv
load_dotenv()

import json
import urllib.request
import urllib.error
import pandas as pd
import yaml
from datetime import datetime
import dateutil.parser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_config():
    with open(os.path.join(PROJECT_ROOT, "config", "config.yaml"), "r") as f:
        return yaml.safe_load(f)


def fetch_active_tennis_sports(api_key):
    """Discover ALL tennis sport keys (active + inactive) and try them all."""
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={api_key}&all=true"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
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
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
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


def _event_book_rows(sport, event, snapshot_ts):
    """Flatten ONE event into one row per (bookmaker, market). Captures ALL
    bookmakers (multi-book best-price + soft-book detection) and the snapshot
    timestamp (line movement / CLV). Pre-match info only — no leakage."""
    p1 = event.get('home_team'); p2 = event.get('away_team')
    commence = event.get('commence_time', '')
    rows = []
    for bk in event.get('bookmakers', []):
        for m in bk.get('markets', []):
            key = m.get('key')
            outs = {o.get('name'): o for o in m.get('outcomes', [])}
            row = {
                "snapshot_ts": snapshot_ts, "commence_time": commence,
                "sport_key": sport, "p1": p1, "p2": p2,
                "bookmaker": bk.get('key'), "market": key,
                "line": None, "price_1": None, "price_2": None,
                "over_under_line": None, "over_price": None, "under_price": None,
            }
            if key == 'h2h' and p1 in outs and p2 in outs:
                row["price_1"] = outs[p1].get('price'); row["price_2"] = outs[p2].get('price')
            elif key == 'spreads' and p1 in outs and p2 in outs:
                row["line"] = outs[p1].get('point')
                row["price_1"] = outs[p1].get('price'); row["price_2"] = outs[p2].get('price')
            elif key == 'totals':
                over = next((o for o in m.get('outcomes', []) if o.get('name', '').lower() == 'over'), None)
                under = next((o for o in m.get('outcomes', []) if o.get('name', '').lower() == 'under'), None)
                if over and under:
                    row["over_under_line"] = over.get('point')
                    row["over_price"] = over.get('price'); row["under_price"] = under.get('price')
            else:
                continue
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

    sport_keys = fetch_active_tennis_sports(api_key)
    all_matches = []

    for sport in sport_keys:
        scope = f"bookmakers={bookmakers}" if bookmakers else f"regions={regions}"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds?apiKey={api_key}&{scope}&markets={markets}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                events = json.loads(response.read().decode('utf-8'))
                if not events:
                    continue

                sport_label = sport.replace('tennis_', '').replace('_', ' ').title()
                print(f"  [+] {sport}: {len(events)} events")

                for event in events:
                    try:
                        p1_name = event.get('home_team', 'Unknown P1')
                        p2_name = event.get('away_team', 'Unknown P2')
                        commence_time = event.get('commence_time', '')

                        try:
                            dt = dateutil.parser.isoparse(commence_time)
                            time_display = dt.strftime("%H:%M")
                            commence_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
                        except:
                            time_display = "Upcoming"
                            commence_iso = ""

                        bookmakers = event.get('bookmakers', [])

                        # Data structures for markets
                        h2h_data = {"o1": 0.0, "o2": 0.0}
                        spread_data = {"line": 0.0, "o1": 0.0, "o2": 0.0}
                        total_data = {"line": 0.0, "over": 0.0, "under": 0.0}
                        source_bookie = "N/A"

                        def extract_markets(bk):
                            nonlocal source_bookie
                            source_bookie = bk['title']
                            for m in bk.get('markets', []):
                                if m['key'] == 'h2h':
                                    for o in m['outcomes']:
                                        if o['name'] == p1_name: h2h_data['o1'] = o['price']
                                        elif o['name'] == p2_name: h2h_data['o2'] = o['price']
                                elif m['key'] == 'spreads':
                                    p1_o = next((o for o in m['outcomes'] if o['name'] == p1_name), None)
                                    p2_o = next((o for o in m['outcomes'] if o['name'] == p2_name), None)
                                    if p1_o and p2_o:
                                        spread_data['line'] = p1_o['point']
                                        spread_data['o1'] = p1_o['price']
                                        spread_data['o2'] = p2_o['price']
                                elif m['key'] == 'totals':
                                    over_o = next((o for o in m['outcomes'] if o['name'].lower() == 'over'), None)
                                    under_o = next((o for o in m['outcomes'] if o['name'].lower() == 'under'), None)
                                    if over_o and under_o:
                                        total_data['line'] = over_o['point']
                                        total_data['over'] = over_o['price']
                                        total_data['under'] = under_o['price']

                        # Select bookmaker by priority (Pinnacle = sharpest odds)
                        preferred = ['pinnacle', 'bet365', 'betfair_ex_eu', 'williamhill', 'betway']
                        selected_bk = None
                        for pref in preferred:
                            selected_bk = next((bk for bk in bookmakers if bk['key'].lower() == pref), None)
                            if selected_bk:
                                break
                        # Fallback to first available
                        if not selected_bk and bookmakers:
                            selected_bk = bookmakers[0]
                        if selected_bk:
                            extract_markets(selected_bk)
                        else:
                            continue

                        if h2h_data['o1'] > 0:
                            match_str = f"[{time_display}] {p1_name} vs {p2_name}"
                            sport_title = event.get('sport_title', sport_label)
                            all_matches.append({
                                "match": match_str,
                                "commence_time": commence_iso,
                                "sport_key": sport,
                                "sport_title": sport_title,
                                "odds_1": h2h_data['o1'],
                                "odds_2": h2h_data['o2'],
                                "spread_line": spread_data['line'],
                                "spread_odds_1": spread_data['o1'],
                                "spread_odds_2": spread_data['o2'],
                                "total_line": total_data['line'],
                                "total_over": total_data['over'],
                                "total_under": total_data['under'],
                                "source": source_bookie,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                    except Exception as e:
                        print(f"Skipping malformed event in {sport}: {e}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # Unknown sport key, skip silently
            elif e.code == 429:
                # Rate-limited on this sport — skip it, keep scanning others.
                # Old behavior (break) killed the whole scan on the first 429.
                print(f"  [!] Rate limit on {sport} — skipping, continuing scan")
                import time as _t
                _t.sleep(2)
                continue
            else:
                continue
        except Exception:
            continue

    return all_matches

def save_to_csv(matches):
    os.makedirs(os.path.join(PROJECT_ROOT, 'data', 'live'), exist_ok=True)
    df = pd.DataFrame(matches)

    if df.empty:
        print("No active tennis matches with valid odds found.")
        df = pd.DataFrame(columns=["match", "odds_1", "odds_2", "spread_line", "spread_odds_1", "spread_odds_2", "total_line", "total_over", "total_under", "source", "timestamp"])
    else:
        df = df.drop_duplicates(subset=['match'])

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
