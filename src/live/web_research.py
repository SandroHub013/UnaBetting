"""
Web Research Module v3.0 — Real-time tennis news & web search.
Priority: Brave Search API (best) > DuckDuckGo HTML > Google News RSS.
"""
import os
import time
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote
from dotenv import load_dotenv

load_dotenv()


class WebResearch:
    """Multi-source web research for tennis news and probability adjustment."""

    _CACHE_TTL = 900  # 15 minutes

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
        })
        self._cache: dict[str, tuple[float, list]] = {}
        self._brave_key = os.getenv("BRAVE_API_KEY", "")
        self._has_brave = bool(self._brave_key and not self._brave_key.startswith("${"))
        self._last_brave_call = 0.0  # Rate limiter: track last API call time

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Domains that produce useless scorecard/livescore noise
    _JUNK_DOMAINS = {
        "flashscore", "sofascore", "livescore", "tennismajors.com/matches",
        "matchstat", "pointsprono", "betsapi", "scoreboard",
    }

    def _is_junk_result(self, item: dict) -> bool:
        """Filter out scorecard pages, livescores, and irrelevant results."""
        title = item.get("title", "").lower()
        snippet = item.get("snippet", "").lower()
        source = item.get("source", "").lower()
        link = item.get("link", "").lower()

        # Junk domains
        for junk in self._JUNK_DOMAINS:
            if junk in source or junk in link:
                return True

        # Scorecard-style titles: "Player A vs Player B - Match ATP"
        if " vs " in title and ("match atp" in title or "match wta" in title
                                or "live score" in title or "scorecard" in title):
            return True

        # Empty/boilerplate snippets
        if snippet and ("this tennis match is between" in snippet
                       or "live tennis match scorecard" in snippet):
            return True

        return False

    def search_player_news(self, player_name: str, max_results: int = 5) -> list[dict]:
        """Search for recent tennis news about a player.
        Filters out scorecard/livescore noise. Focuses on actionable news.
        """
        cache_key = f"player:{player_name.lower()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self._has_brave:
            # Query focused on actual news, not scores
            raw = self._brave_news_search(
                f'"{player_name}" tennis injury OR fitness OR withdrawal OR form OR clay OR practice',
                max_results + 5,  # Fetch extra to compensate for filtering
            )
            # Filter junk
            results = [r for r in raw if not self._is_junk_result(r)][:max_results]

            if not results:
                # Fallback: broader web search
                raw = self._brave_web_search(
                    f'"{player_name}" tennis news 2026',
                    max_results + 3,
                )
                results = [r for r in raw if not self._is_junk_result(r)][:max_results]
        else:
            results = self._google_news_rss(f"{player_name} tennis", max_results)

        self._set_cached(cache_key, results)
        return results

    def search_tournament_news(self, tournament_name: str, max_results: int = 5) -> list[dict]:
        """Search for tournament-level news (weather, withdrawals, surface, schedule)."""
        cache_key = f"tourney:{tournament_name.lower()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self._has_brave:
            # Single query covers withdrawals + conditions
            results = self._brave_news_search(
                f"{tournament_name} tennis 2026 withdrawal OR weather OR conditions",
                max_results,
            )
            if not results:
                results = self._brave_web_search(f"{tournament_name} tennis 2026", max_results)
        else:
            results = self._google_news_rss(f"{tournament_name} tennis 2026", max_results)

        self._set_cached(cache_key, results)
        return results

    def search_web(self, query: str, max_results: int = 5) -> list[dict]:
        """General web search. Used by the agent for flexible queries."""
        cache_key = f"web:{query.lower()}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self._has_brave:
            results = self._brave_web_search(query, max_results)
        else:
            results = self._duckduckgo_search(query, max_results)

        self._set_cached(cache_key, results)
        return results

    def fetch_all_news_for_matches(self, predictions: list) -> dict:
        """Batch-fetch news for all players across all matches.

        Returns: {
            match_str: {
                "p1_news": [{"title": ..., "source": ..., "snippet": ...}],
                "p2_news": [...],
                "tourney_news": [...]
            }
        }
        """
        result = {}
        seen_players: dict[str, list] = {}
        tourney_name = ""

        for p in predictions:
            match_str = p.get("match", "")
            p1_name, p2_name = self._parse_player_names(match_str)
            if not p1_name:
                continue

            if not tourney_name:
                tourney_name = (
                    p.get("forensics", {}).get("tourney_name", "")
                    or p.get("sport_title", "")
                )

            # Fetch per player (cached, so duplicates are free)
            # Rate limiting handled internally by _brave_rate_wait()
            if p1_name.lower() not in seen_players:
                seen_players[p1_name.lower()] = self.search_player_news(p1_name)
            if p2_name.lower() not in seen_players:
                seen_players[p2_name.lower()] = self.search_player_news(p2_name)

            result[match_str] = {
                "p1_news": seen_players.get(p1_name.lower(), []),
                "p2_news": seen_players.get(p2_name.lower(), []),
                "tourney_news": [],
            }

        # Tournament news once
        if tourney_name:
            tourney_news = self.search_tournament_news(tourney_name)
            for match_str in result:
                result[match_str]["tourney_news"] = tourney_news

        return result

    def format_news_for_prompt(self, news_data: dict) -> str:
        """Format all news into a concise text block for LLM context."""
        if not news_data:
            return "Nessuna news trovata.\n"

        lines = []
        for match_str, data in news_data.items():
            p1_news = data.get("p1_news", [])
            p2_news = data.get("p2_news", [])
            if not p1_news and not p2_news:
                continue

            lines.append(f"\nMATCH: {match_str}")
            if p1_news:
                lines.append("  P1 News:")
                for n in p1_news[:3]:
                    lines.append(f"    - {n['title']} ({n.get('source', '?')})")
                    if n.get("snippet"):
                        lines.append(f"      >>> {n['snippet'][:250]}")
            if p2_news:
                lines.append("  P2 News:")
                for n in p2_news[:3]:
                    lines.append(f"    - {n['title']} ({n.get('source', '?')})")
                    if n.get("snippet"):
                        lines.append(f"      >>> {n['snippet'][:250]}")

        any_tourney = []
        for data in news_data.values():
            if data.get("tourney_news"):
                any_tourney = data["tourney_news"]
                break
        if any_tourney:
            lines.append("\nTOURNAMENT NEWS:")
            for n in any_tourney[:3]:
                lines.append(f"  - {n['title']} ({n.get('source', '?')})")
                if n.get("snippet"):
                    lines.append(f"    >>> {n['snippet'][:200]}")

        return "\n".join(lines) if lines else "Nessuna news rilevante trovata.\n"

    # ==================================================================
    # BRAVE SEARCH API (Primary — best quality)
    # ==================================================================

    def _brave_rate_wait(self):
        """Enforce min 1.1s between Brave API calls (free tier: 1 req/sec)."""
        elapsed = time.time() - self._last_brave_call
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self._last_brave_call = time.time()

    def _brave_news_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Brave News Search API — returns recent news with snippets."""
        self._brave_rate_wait()

        url = "https://api.search.brave.com/res/v1/news/search"
        params = {
            "q": query,
            "count": max_results,
            "freshness": "pw",  # past week
        }
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._brave_key,
        }

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            # Retry once on 429 (rate limit)
            if resp.status_code == 429:
                time.sleep(2)
                self._last_brave_call = time.time()
                resp = self.session.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "source": item.get("meta_url", {}).get("hostname", ""),
                "date": item.get("age", ""),
                "link": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return results

    def _brave_web_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Brave Web Search API — general search with snippets."""
        self._brave_rate_wait()

        url = "https://api.search.brave.com/res/v1/web/search"
        params = {
            "q": query,
            "count": max_results,
        }
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._brave_key,
        }

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 429:
                time.sleep(2)
                self._last_brave_call = time.time()
                resp = self.session.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results = []
        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "source": item.get("meta_url", {}).get("hostname", ""),
                "date": item.get("age", ""),
                "link": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return results

    # ==================================================================
    # FALLBACK: Google News RSS
    # ==================================================================

    def _google_news_rss(self, query: str, max_results: int = 5) -> list[dict]:
        """Fetch headlines from Google News RSS feed (no snippets)."""
        encoded = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
        except Exception:
            return []

        try:
            soup = BeautifulSoup(resp.content, "lxml-xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "html.parser")

        items = soup.find_all("item")
        results = []
        for item in items[:max_results]:
            title = item.find("title")
            source = item.find("source")
            pub_date = item.find("pubDate")

            results.append({
                "title": title.get_text(strip=True) if title else "",
                "source": source.get_text(strip=True) if source else "",
                "date": pub_date.get_text(strip=True) if pub_date else "",
                "link": "",
                "snippet": "",
            })

        return results

    # ==================================================================
    # FALLBACK: DuckDuckGo HTML Search
    # ==================================================================

    def _duckduckgo_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search DuckDuckGo HTML version (no API key needed)."""
        encoded = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
        except Exception:
            return []

        try:
            soup = BeautifulSoup(resp.content, "html.parser")
        except Exception:
            return []

        results = []
        for result_div in soup.select(".result")[:max_results]:
            title_tag = result_div.select_one(".result__a")
            snippet_tag = result_div.select_one(".result__snippet")

            title = title_tag.get_text(strip=True) if title_tag else ""
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            link = ""
            if title_tag and title_tag.get("href"):
                href = title_tag["href"]
                if "uddg=" in href:
                    match = re.search(r'uddg=([^&]+)', href)
                    if match:
                        link = unquote(match.group(1))
                else:
                    link = href

            if title:
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "source": "",
                    "link": link,
                    "date": "",
                })

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_player_names(match_str: str) -> tuple[str, str]:
        """Extract P1, P2 names from '[HH:MM] P1 vs P2'."""
        try:
            names_part = match_str.split("] ")[1]
            p1, p2 = names_part.split(" vs ")
            return p1.strip(), p2.strip()
        except Exception:
            return "", ""

    def _get_cached(self, key: str):
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._CACHE_TTL:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data):
        self._cache[key] = (time.time(), data)


if __name__ == "__main__":
    wr = WebResearch()
    engine = "Brave API" if wr._has_brave else "Fallback (RSS+DDG)"
    print(f"Search engine: {engine}\n")

    print("=== Player News ===")
    news = wr.search_player_news("Jannik Sinner")
    print(f"Found {len(news)} items:")
    for n in news[:3]:
        print(f"  TITLE:   {n['title'][:80]}")
        print(f"  SOURCE:  {n.get('source', '?')}")
        print(f"  SNIPPET: {n.get('snippet', '(none)')[:150]}")
        print()

    print("=== Web Search ===")
    web = wr.search_web("tennis Monte Carlo 2026 results")
    print(f"Found {len(web)} results:")
    for w in web[:3]:
        print(f"  TITLE:   {w['title'][:80]}")
        print(f"  SNIPPET: {w.get('snippet', '(none)')[:150]}")
        print()
