"""
Agentic Web Research Engine v2.0
================================
True ReAct agent: LLM decides WHAT to search, reads full articles,
digs deeper when needed, consults Tennis Abstract for stats.

Improvements over v1.0 (based on architecture review):
  1. AUTHORITATIVE SOURCE FILTERING - searches prioritize L'Equipe,
     Gazzetta, Tennis Abstract, ATP/WTA official, BBC Sport, ESPN
  2. DEEP CONTENT EXTRACTION - fetch_article extracts key paragraphs
     with tennis-keyword scoring, not just raw text dump
  3. PERSISTENT RESEARCH CACHE - JSON file cache survives across scans,
     avoids redundant searches within TTL window

Tools available to the agent:
  1. search_tennis_news(query) - Brave News API, filtered for tennis sources
  2. search_web(query) - General web search
  3. fetch_article(url) - Deep content extraction with relevance scoring
  4. get_player_stats(player_name) - Tennis Abstract structured stats
  5. done(adjustments) - Agent returns final adjustments
"""

import os
import re
import json
import time
import ssl
import logging
import hashlib
import urllib.request
import urllib.error
import yaml
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv

JSON_CONTENT_TYPE = "application/json"

log = logging.getLogger("agentic")

load_dotenv()

MAX_AGENT_ITERATIONS = 8
MAX_ADJUSTMENT = 0.15
MIN_PROB = 0.05
MAX_PROB = 0.95

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_FILE = CACHE_DIR / "research_cache.json"
CACHE_TTL = 1200  # 20 min — injury/walkover news changes within hours of match


# ============================================================
# AUTHORITATIVE SOURCES — prioritized in search results
# ============================================================

# Domains we TRUST for tennis news (boosted in results)
TRUSTED_DOMAINS = {
    "tennisabstract.com", "atptour.com", "wtatennis.com",
    "lequipe.fr", "gazzetta.it", "bbc.com", "bbc.co.uk",
    "espn.com", "tennismajors.com", "tennishead.net",
    "tennisworldusa.org", "tennis.com", "eurosport.com",
    "reuters.com", "theguardian.com", "skysport.it",
    "ubitennis.com", "tennisprofessional.it",
}

# Domains that produce JUNK (livescores, scorecards)
JUNK_DOMAINS = {
    "flashscore", "sofascore", "livescore", "matchstat",
    "betsapi", "scoreboard", "pointsprono", "oddschecker",
    "betway", "bet365", "williamhill",
}

# Keywords that signal actionable tennis news
ACTIONABLE_KEYWORDS = [
    "injury", "injured", "withdrawal", "withdrew", "retired",
    "fitness", "doubt", "uncertain", "pulled out", "skip",
    "comeback", "return", "practice", "training",
    "infortunio", "ritiro", "ritirato", "dubbio", "assenza",
    "forfait", "blessure", "abandon",
]


# ============================================================
# PERSISTENT RESEARCH CACHE
# ============================================================

#: page furniture that never carries article text
_NOISE_TAGS = ("script", "style", "nav", "header", "footer",
               "aside", "iframe", "form", "button")

#: tennis vocabulary — weaker signal than ACTIONABLE_KEYWORDS but still on-topic
_TENNIS_CONTEXT = ("set", "match", "tournament", "round", "clay",
                   "hard court", "grass", "serve", "forehand",
                   "backhand", "coach", "physio", "MRI", "scan",
                   "recovery", "pain", "discomfort", "confident",
                   "semifinal", "quarterfinal", "final", "title")


def _article_body(html):
    """The <article>/<main>/<body> element with the page furniture stripped out."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()
    return soup.find("article") or soup.find("main") or soup.find("body")


def _paragraph_score(text):
    """How useful a paragraph is for a betting decision."""
    text_lower = text.lower()
    score = 3 * sum(1 for kw in ACTIONABLE_KEYWORDS if kw in text_lower)
    score += sum(1 for kw in _TENNIS_CONTEXT if kw in text_lower)
    # capitalised words usually mean player names, i.e. concrete context
    if len(re.findall(r'\b[A-Z][a-z]+\b', text)) >= 2:
        score += 1
    return score


def _top_paragraphs(paragraphs, keep=8, fallback=5, max_chars=2500):
    """The highest-scoring paragraphs, joined and truncated."""
    scored = [(_paragraph_score(t), t)
              for t in (p.get_text(strip=True) for p in paragraphs)
              if len(t) >= 20]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [text for score, text in scored if score > 0][:keep]
    if not top:
        top = [text for _, text in scored[:fallback]]
    content = "\n\n".join(top)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n[... TRUNCATED]"
    return content


#: line fragments that mark a Tennis Abstract row as worth keeping
_TA_STAT_KEYWORDS = (
    "elo", "rank", "record", "ytd", "last 52", "surface",
    "clay", "hard", "grass", "indoor", "outdoor",
    "vs top", "recent", "streak", "current", "peak",
    "win", "loss", "titles", "finals", "h2h",
    "serve", "return", "break point", "tiebreak",
)


def _ta_slugs(parts):
    """Tennis Abstract player slugs to try, most likely first."""
    first = parts[0]
    last = "".join(parts[1:])
    return [
        f"{first[0]}{last}".lower(),     # JSinner
        "".join(parts).lower(),          # janniksinner
        f"{first}{last}".lower(),        # janniksinner (redundant but safe)
    ]


def _ta_table_rows(soup, tables_to_read=5):
    """Cells of the first few tables, one pipe-joined line per row."""
    rows_out = []
    for table in soup.find_all("table")[:tables_to_read]:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            cell_text = " | ".join(c.get_text(strip=True) for c in cells)
            if cell_text.strip():
                rows_out.append(cell_text)
    return rows_out


def _ta_keyword_lines(text):
    lines = []
    for line in text.split("\n"):
        line_s = line.strip()
        if len(line_s) < 5:
            continue
        if any(kw in line_s.lower() for kw in _TA_STAT_KEYWORDS):
            lines.append(line_s)
    return lines


def _ta_summary(soup, player_name, keep=50, max_chars=1800):
    """Table rows plus keyword lines, deduplicated and truncated."""
    text = soup.get_text(separator="\n", strip=True)
    seen = set()
    all_stats = []
    for line in _ta_table_rows(soup) + _ta_keyword_lines(text):
        if line not in seen and len(line) > 5:
            seen.add(line)
            all_stats.append(line)

    if not all_stats:
        return f"Tennis Abstract for {player_name}:\n{text[:1200]}"
    stats_text = "\n".join(all_stats[:keep])
    if len(stats_text) > max_chars:
        stats_text = stats_text[:max_chars] + "\n[... TRUNCATED]"
    return f"Tennis Abstract stats for {player_name}:\n\n{stats_text}"


def _tool_arguments(tool_call):
    """Arguments of a tool call; a malformed JSON blob means no arguments."""
    raw = tool_call.get("function", {}).get("arguments", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class ResearchCache:
    """JSON-based persistent cache for research results.
    Survives across scans — avoids redundant API calls within TTL.
    """

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        # Prune expired entries
        now = time.time()
        self._data = {k: v for k, v in self._data.items()
                      if now - v.get("ts", 0) < CACHE_TTL}

    def _save(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry and time.time() - entry.get("ts", 0) < CACHE_TTL:
            return entry["result"]
        return None

    def set(self, key: str, result: str):
        self._data[key] = {"result": result, "ts": time.time()}
        self._save()

    def make_key(self, tool: str, args: str) -> str:
        raw = f"{tool}:{args}"
        return hashlib.md5(raw.encode()).hexdigest()


# ============================================================
# TOOLS — Functions the agent can call
# ============================================================

class AgentTools:
    """Tools available to the research agent."""

    def __init__(self):
        self._brave_key = os.getenv("BRAVE_API_KEY", "")
        self._has_brave = bool(self._brave_key and not self._brave_key.startswith("${"))
        self._last_brave_call = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8,fr;q=0.7",
        })
        self.cache = ResearchCache()

    # --- Tool 1: Tennis News Search (AUTHORITATIVE) ---
    def search_tennis_news(self, query: str, max_results: int = 6) -> str:
        """Search recent tennis news via Brave News API.
        Results are filtered and ranked: trusted sources first, junk removed.
        """
        cache_key = self.cache.make_key("news", query)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self._has_brave:
            return "[ERROR] No Brave API key configured."

        self._brave_rate_wait()
        url = "https://api.search.brave.com/res/v1/news/search"
        params = {"q": query, "count": max_results + 5, "freshness": "pw"}
        headers = {
            "Accept": JSON_CONTENT_TYPE,
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._brave_key,
        }

        try:
            resp = self._session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 429:
                time.sleep(2)
                self._last_brave_call = time.time()
                resp = self._session.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"[ERROR] News search failed: {e}"

        raw_items = data.get("results", [])

        # Filter junk, then sort: trusted sources first
        filtered = []
        for item in raw_items:
            hostname = item.get("meta_url", {}).get("hostname", "").lower()
            link = item.get("url", "").lower()

            # Skip junk
            if any(j in hostname or j in link for j in JUNK_DOMAINS):
                continue

            is_trusted = any(t in hostname for t in TRUSTED_DOMAINS)
            # Score: actionable keywords in title/description
            text = (item.get("title", "") + " " + item.get("description", "")).lower()
            keyword_hits = sum(1 for kw in ACTIONABLE_KEYWORDS if kw in text)

            filtered.append({
                "item": item,
                "trusted": is_trusted,
                "keyword_score": keyword_hits,
                "hostname": hostname,
            })

        # Sort: trusted first, then by keyword relevance
        filtered.sort(key=lambda x: (x["trusted"], x["keyword_score"]), reverse=True)

        results = []
        for i, f in enumerate(filtered[:max_results], 1):
            item = f["item"]
            title = item.get("title", "No title")
            snippet = item.get("description", "")[:350]
            link = item.get("url", "")
            age = item.get("age", "")
            source = f["hostname"]
            trust_marker = " [TRUSTED]" if f["trusted"] else ""
            results.append(
                f"  [{i}] {title} ({source}{trust_marker}, {age})\n"
                f"      URL: {link}\n"
                f"      {snippet}"
            )

        if not results:
            result = f"[NO RESULTS] No tennis news found for: {query}"
        else:
            result = f"Tennis news for '{query}':\n\n" + "\n\n".join(results)

        self.cache.set(cache_key, result)
        return result

    # --- Tool 2: General Web Search ---
    def search_web(self, query: str, max_results: int = 5) -> str:
        """General web search via Brave API."""
        cache_key = self.cache.make_key("web", query)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self._has_brave:
            return "[ERROR] No Brave API key configured."

        self._brave_rate_wait()
        url = "https://api.search.brave.com/res/v1/web/search"
        params = {"q": query, "count": max_results}
        headers = {
            "Accept": JSON_CONTENT_TYPE,
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._brave_key,
        }

        try:
            resp = self._session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 429:
                time.sleep(2)
                self._last_brave_call = time.time()
                resp = self._session.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"[ERROR] Web search failed: {e}"

        results = []
        for i, item in enumerate(data.get("web", {}).get("results", [])[:max_results], 1):
            title = item.get("title", "No title")
            snippet = item.get("description", "")[:300]
            link = item.get("url", "")
            results.append(f"  [{i}] {title}\n      URL: {link}\n      {snippet}")

        result = (f"Web results for '{query}':\n\n" + "\n\n".join(results)) if results else f"[NO RESULTS] for: {query}"
        self.cache.set(cache_key, result)
        return result

    # --- Tool 3: Deep Article Fetcher ---
    def fetch_article(self, url: str) -> str:
        """Fetch article and extract KEY PARAGRAPHS using relevance scoring.
        Not a raw text dump — focuses on injury/fitness/form paragraphs.
        """
        cache_key = self.cache.make_key("article", url)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        try:
            resp = self._session.get(url, timeout=12, allow_redirects=True)
            resp.raise_for_status()
            article = _article_body(resp.text)
            if not article:
                return "[ERROR] Could not extract article content."

            paragraphs = article.find_all(["p", "li", "h2", "h3"])
            if not paragraphs:
                text = article.get_text(separator="\n", strip=True)[:1500]
                result = f"Article from {url}:\n\n{text}"
                self.cache.set(cache_key, result)
                return result

            content = _top_paragraphs(paragraphs)
            result = f"Key content from {url}:\n\n{content}"
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            return f"[ERROR] Failed to fetch {url}: {e}"

    # --- Tool 4: Tennis Abstract Player Stats ---
    def get_player_stats(self, player_name: str) -> str:
        """Scrape Tennis Abstract for player stats: ELO, form, surface records."""
        cache_key = self.cache.make_key("ta_stats", player_name.lower())
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        parts = player_name.strip().split()
        if len(parts) < 2:
            return f"[ERROR] Cannot parse player name: {player_name}"

        for slug in _ta_slugs(parts):
            url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={slug}"
            try:
                resp = self._session.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.find("title")
                if title and "not found" in title.text.lower():
                    continue

                result = _ta_summary(soup, player_name)
                self.cache.set(cache_key, result)
                return result

            except Exception:
                continue

        return f"[NOT FOUND] Could not find {player_name} on Tennis Abstract. Try searching the web instead."

    # --- Rate Limiting ---
    def _brave_rate_wait(self):
        elapsed = time.time() - self._last_brave_call
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self._last_brave_call = time.time()


# ============================================================
# TOOL DEFINITIONS (OpenRouter function calling schema)
# ============================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_tennis_news",
            "description": (
                "Search for recent tennis news (past week). Results are filtered "
                "for authoritative sources (L'Equipe, Gazzetta, BBC, ESPN, ATP) and "
                "ranked by relevance. Use for injuries, withdrawals, form updates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "News search query. Be specific: 'Sinner injury update April 2026'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "General web search. Use for broader queries, H2H records, tournament info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Web search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_article",
            "description": (
                "Fetch and read a web article in depth. Extracts the KEY paragraphs "
                "about injuries, fitness, form — not the full page. Use when a search "
                "snippet mentions something important but you need the full detail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch. Must be http/https."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_stats",
            "description": (
                "Get player statistics from Tennis Abstract: current ELO, ranking, "
                "win/loss record, surface records, recent form, streak. "
                "Use this for EVERY player to understand their current form."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": "Full player name: 'Jannik Sinner'"
                    }
                },
                "required": ["player_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": (
                "FINISH research and return probability adjustments. "
                "Call this ONLY when you have enough info for ALL matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "adjustments": {
                        "type": "array",
                        "description": "One adjustment object per match.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "match": {"type": "string", "description": "Exact match string from input"},
                                "adjustment": {"type": "number", "description": "-0.15 to +0.15. Positive favors P1."},
                                "confidence": {"type": "number", "description": "0.0 to 1.0"},
                                "reason": {"type": "string", "description": "Brief reasoning, max 30 words"},
                                "sources": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "URLs or source names consulted"
                                }
                            },
                            "required": ["match", "adjustment", "confidence", "reason"]
                        }
                    }
                },
                "required": ["adjustments"]
            }
        }
    },
]


# ============================================================
# AGENT SYSTEM PROMPT
# ============================================================

AGENT_SYSTEM_PROMPT = """\
Sei un agente di ricerca specializzato in tennis betting. Analizzi match \
imminenti e determini se le probabilita' ML necessitano aggiustamenti \
basati su informazioni che il modello non puo' conoscere.

HAI 5 STRUMENTI:
- search_tennis_news(query): notizie recenti da fonti autorevoli
- search_web(query): ricerca web generale
- fetch_article(url): leggi un articolo in profondita'
- get_player_stats(player_name): statistiche Tennis Abstract (ELO, forma, record)
- done(adjustments): concludi e restituisci risultati

PROCEDURA (obbligatoria):
1. Per ogni giocatore: get_player_stats per ELO, forma recente, record superficie
2. Per ogni giocatore: search_tennis_news per infortuni, ritiri, condizioni
3. Se un articolo sembra rilevante: fetch_article per leggere i dettagli
4. Una ricerca per il torneo: meteo, condizioni, ritiri
5. Sintetizza e chiama done()

REGOLE ADJUSTMENT (relativo a P1):
- Infortunio confermato: -0.05 a -0.15
- Ritiro annunciato: -0.15
- Rientro dopo >60gg: -0.03 a -0.08
- Forma eccezionale non nel modello: +0.03 a +0.08
- Meteo sfavorevole a uno stile: -0.02 a -0.05
- Nessuna news: adjustment 0.0, confidence 1.0

IMPORTANTE:
- Fai ricerche SPECIFICHE (nome giocatore + keyword)
- Leggi SEMPRE gli articoli quando trovi notizie rilevanti
- Non inventare info — solo fonti concrete
- Massimo 6-8 tool calls totali\
"""


# ============================================================
# REACT AGENT LOOP
# ============================================================

class AgenticResearcher:
    """ReAct agent that autonomously researches tennis matches."""

    def __init__(self):
        self.tools = AgentTools()
        self._api_key = os.getenv("OPENROUTER_API_KEY", "")

        try:
            with open("config/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            self._model = config.get("news_adjustment", {}).get("model", "z-ai/glm-5.1")
        except Exception:
            self._model = "z-ai/glm-5.1"

    def _run_tool(self, func_name, func_args):
        """Dispatch one tool call to the AgentTools instance."""
        if func_name == "search_tennis_news":
            return self.tools.search_tennis_news(func_args.get("query", ""))
        if func_name == "search_web":
            return self.tools.search_web(func_args.get("query", ""))
        if func_name == "fetch_article":
            return self.tools.fetch_article(func_args.get("url", ""))
        if func_name == "get_player_stats":
            return self.tools.get_player_stats(func_args.get("player_name", ""))
        return f"[ERROR] Unknown tool: {func_name}"

    def research_matches(self, predictions: list) -> list[dict]:
        """Run the agentic research loop for match predictions."""
        if not self._api_key:
            print("  [Agent] No OpenRouter API key. Skipping.")
            return []

        context = self._build_initial_context(predictions)
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        print(f"  [Agent] Starting research for {len(predictions)} matches...")
        tool_call_count = 0

        for iteration in range(MAX_AGENT_ITERATIONS):
            response = self._call_llm(messages)
            if response is None:
                print(f"  [Agent] LLM call failed at iteration {iteration + 1}.")
                break

            message = response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                content = message.get("content", "")
                if content:
                    print(f"  [Agent] Thought: {content[:120]}...")
                messages.append({"role": "assistant", "content": content})
                if iteration > 0:
                    break
                continue

            messages.append(message)

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "")
                func_args = _tool_arguments(tc)
                tc_id = tc.get("id", f"call_{iteration}_{tool_call_count}")

                tool_call_count += 1
                args_preview = json.dumps(func_args, ensure_ascii=False)[:80]
                print(f"  [Agent] [{tool_call_count}] {func_name}({args_preview})")

                if func_name == "done":
                    adjustments = func_args.get("adjustments", [])
                    print(f"  [Agent] Research complete. {len(adjustments)} adjustments.")
                    messages.append({
                        "role": "tool", "tool_call_id": tc_id,
                        "content": json.dumps({"status": "ok"}),
                    })
                    return adjustments

                messages.append({
                    "role": "tool", "tool_call_id": tc_id,
                    "content": self._run_tool(func_name, func_args)[:3000],
                })

        print("  [Agent] Max iterations. Forcing completion...")
        return self._force_completion(messages)

    def _build_initial_context(self, predictions: list) -> str:
        lines = [
            "Analizza questi match e determina se servono aggiustamenti.",
            "Per ogni giocatore: controlla stats Tennis Abstract + cerca notizie recenti.",
            ""
        ]

        for p in predictions:
            match_str = p.get("match", "?")
            f = p.get("forensics", {})
            lines.append(f"MATCH: {match_str}")
            lines.append(f"  Torneo: {f.get('tourney_name', '?')} ({f.get('tourney_level', '?')})")
            lines.append(f"  Superficie: {p.get('surface', '?')}")
            lines.append(f"  ML Prob: P1={p.get('prob_1', 0):.1%}  P2={p.get('prob_2', 0):.1%}")
            lines.append(f"  Odds: P1={p.get('odds_1', 0):.2f}  P2={p.get('odds_2', 0):.2f}")
            lines.append(f"  P1: {f.get('p1_name', '?')} (Rank {f.get('p1_rank', '?')}, ELO {f.get('p1_elo', '?')}, Form {f.get('p1_form', '?')})")
            lines.append(f"  P2: {f.get('p2_name', '?')} (Rank {f.get('p2_rank', '?')}, ELO {f.get('p2_elo', '?')}, Form {f.get('p2_form', '?')})")
            lines.append(f"  H2H: {f.get('p1_h2h', 0)}-{f.get('p2_h2h', 0)}")
            lines.append("")

        lines.append("Inizia: get_player_stats per ogni giocatore, poi search_tennis_news.")
        return "\n".join(lines)

    def _call_llm(self, messages: list) -> dict | None:
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": 0.2,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": JSON_CONTENT_TYPE,
            "X-Title": "Tennis Pro Terminal - Agentic Research",
        }
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        self._last_error = None  # surface to run_agentic_research for failure reason
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=data, headers=headers, method="POST",
                )
                with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if self._handle_http_error(e, attempt):
                    continue
                return None
            except OSError as e:
                if attempt < 2:
                    log.warning("llm_network attempt=%d err=%r", attempt + 1, e)
                    time.sleep(3)
                    continue
                log.error("llm_network_final err=%r", e)
                self._last_error = "network_timeout"
                return None
            except Exception as e:
                log.exception("llm_unexpected err=%r", e)
                self._last_error = f"unexpected_{type(e).__name__}"
                return None
        return None

    def _handle_http_error(self, e, attempt):
        """True to retry. 429 and 5xx are transient; a 4xx fails fast."""
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        transient = e.code == 429 or 500 <= e.code < 600
        if transient and attempt < 2:
            log.warning("llm_http_%s attempt=%d body=%s", e.code, attempt + 1, body[:150])
            time.sleep(5 if e.code == 429 else 3)
            return True
        log.error("llm_http_final code=%s body=%s", e.code, body[:150])
        self._last_error = f"http_{e.code}"
        return False

    def _force_completion(self, messages: list) -> list[dict]:
        messages.append({
            "role": "user",
            "content": (
                "Limite iterazioni raggiunto. Chiama done() ORA con gli aggiustamenti "
                "basati su quello che hai trovato. Se non hai info, usa adjustment 0.0."
            ),
        })
        response = self._call_llm(messages)
        if response is None:
            return []

        message = response.get("choices", [{}])[0].get("message", {})
        for tc in message.get("tool_calls", []):
            if tc.get("function", {}).get("name") == "done":
                try:
                    return json.loads(tc["function"]["arguments"]).get("adjustments", [])
                except Exception:
                    pass

        # Last resort: parse content as JSON
        try:
            return json.loads(message.get("content", ""))
        except Exception:
            return []


# ============================================================
# PUBLIC API
# ============================================================

def _stamp_failure(predictions: list, reason: str) -> list:
    """Tag every prediction with a structured failure reason so downstream
    consumers (TUI, fallback router) can see *why* nothing was applied."""
    for p in predictions:
        if "news_adjustment" not in p:
            p["news_adjustment"] = {"applied": False, "reason": reason}
    return predictions


def run_agentic_research(predictions: list) -> list:
    """Run agentic research and apply adjustments to predictions.
    Drop-in replacement for run_news_adjustment().

    Every prediction ends up with `news_adjustment.applied` (True|False) and,
    on failure, a named `reason` — callers no longer see silent 0/N.
    """
    if not predictions:
        return predictions

    agent = AgenticResearcher()
    try:
        adjustments = agent.research_matches(predictions)
    except Exception as e:
        log.exception("research_failed err=%r", e)
        return _stamp_failure(predictions, f"research_exception:{type(e).__name__}")

    if not adjustments:
        reason = getattr(agent, "_last_error", None) or "no_adjustments_returned"
        log.warning("no_adjustments reason=%s", reason)
        return _stamp_failure(predictions, reason)

    adj_map = {a.get("match", ""): a for a in adjustments if a.get("match")}
    adjusted_count = 0

    for p in predictions:
        match_str = p.get("match", "")
        adj = adj_map.get(match_str)

        if adj is None:
            p.setdefault("news_adjustment", {"applied": False, "reason": "no_match_in_response"})
            continue
        if abs(adj.get("adjustment", 0)) < 0.001:
            p["news_adjustment"] = {
                "applied": False,
                "reason": "no_news_impact",
                "confidence": adj.get("confidence", 0.0),
                "adjustment": adj.get("adjustment", 0.0),
                "sources": adj.get("sources", []),
            }
            continue

        raw_adj = adj["adjustment"]
        confidence = adj.get("confidence", 0.5)
        effective_adj = raw_adj * confidence
        effective_adj = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, effective_adj))

        p["raw_prob_1"] = p.get("raw_prob_1", p["prob_1"])
        p["raw_prob_2"] = p.get("raw_prob_2", p["prob_2"])

        new_p1 = max(MIN_PROB, min(MAX_PROB, p["prob_1"] + effective_adj))
        new_p2 = max(MIN_PROB, min(MAX_PROB, 1.0 - new_p1))
        p["prob_1"] = new_p1
        p["prob_2"] = new_p2

        # Recalculate ROI edge, matching base inference and passive news adjustment.
        edge_1 = (p["odds_1"] * new_p1) - 1
        edge_2 = (p["odds_2"] * new_p2) - 1
        p["edge"] = max(edge_1, edge_2)
        p["value_side"] = 1 if edge_1 > edge_2 else 2

        p["news_adjustment"] = {
            "applied": True,
            "adjustment": raw_adj,
            "confidence": confidence,
            "effective": effective_adj,
            "reason": adj.get("reason", ""),
            "sources": adj.get("sources", []),
        }
        adjusted_count += 1

    # Ensure every prediction has structured news_adjustment
    for p in predictions:
        p.setdefault("news_adjustment", {"applied": False, "reason": "no_match_in_response"})

    log.info("applied=%d/%d", adjusted_count, len(predictions))
    print(f"  [Agent] Applied adjustments to {adjusted_count}/{len(predictions)} matches.")
    return predictions


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    pred_path = "data/live/predictions.json"
    try:
        with open(pred_path) as f:
            preds = json.load(f)
        print(f"Loaded {len(preds)} predictions from {pred_path}")
        result = run_agentic_research(preds)
        for p in result:
            adj = p.get("news_adjustment")
            if adj:
                print(f"  {p['match']}: adj={adj['effective']:+.3f} ({adj['reason']})")
                if adj.get("sources"):
                    print(f"    Sources: {', '.join(adj['sources'][:3])}")
            else:
                print(f"  {p['match']}: no adjustment")
    except FileNotFoundError:
        print(f"No predictions at {pred_path}. Run inference first.")
