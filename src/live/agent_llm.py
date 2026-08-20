"""
Sandro — AI Betting Analyst with Smart Query Routing.
Classifies user queries, injects conditional context, supports web search.
"""
import json
import re
import urllib.request
import urllib.error
import ssl
import yaml
import os
from dotenv import load_dotenv
load_dotenv()

from src.live.web_research import WebResearch


def _venue_line(p, f):
    surface = p.get("surface", f.get("surface", "?"))
    tourney = f.get("tourney_name", "")
    if not (surface or tourney):
        return ""
    suffix = f" ({tourney})" if tourney else ""
    return f"  Superficie: {surface}{suffix}\n"


def _market_line(label, model_value, market_value, edge, fmt):
    tag = f" -> VALORE {edge}" if edge else ""
    return (f"  {label}: ML {fmt.format(model_value)} "
            f"vs Linea {fmt.format(market_value)}{tag}\n")


def _news_line(p):
    adj = p.get("news_adjustment")
    if not (adj and adj.get("applied")):
        return ""
    raw_p1 = p.get("raw_prob_1", p["prob_1"])
    return (f"  NEWS: {adj['reason']} (adj: {adj['effective']:+.3f}, "
            f"conf: {adj['confidence']:.0%})\n"
            f"  Prob pre-news: {raw_p1:.1%} -> post-news: {p['prob_1']:.1%}\n")


def _prediction_block(p):
    """One match, as the analysis prompt sees it."""
    f = p.get('forensics', {})
    conf_tag = " [LOW CONFIDENCE]" if p.get('low_confidence', False) else ""
    return (
        f"MATCH: {p['match']}{conf_tag}\n"
        f"  H2H: P1 {p['prob_1']:.1%} @{p['odds_1']:.2f} | "
        f"P2 {p['prob_2']:.1%} @{p['odds_2']:.2f}\n"
        f"  Edge: {p['edge']:+.1%} (lato P{p.get('value_side', '?')})\n"
        + _venue_line(p, f)
        + (f"  ELO: P1 {f.get('p1_elo', 'N/A')} (sup: {f.get('p1_surface_elo', 'N/A')}) | "
           f"P2 {f.get('p2_elo', 'N/A')} (sup: {f.get('p2_surface_elo', 'N/A')})\n")
        + f"  Forma: P1 {f.get('p1_form', 'N/A')} | P2 {f.get('p2_form', 'N/A')}\n"
        + f"  H2H: {f.get('p1_h2h', 0)} - {f.get('p2_h2h', 0)}\n"
        + _market_line("Spread", f.get('exp_game_diff', 0), f.get('market_spread', 0),
                       f.get('spread_edge', ''), "{:+.1f}")
        + _market_line("Totals", f.get('exp_total_games', 0), f.get('market_total', 0),
                       f.get('totals_edge', ''), "{:.1f}")
        + _news_line(p)
        + "\n"
    )


class AgentLLM:
    """
    Sandro - AI Betting Analyst powered by OpenRouter.
    Routes queries: chat / analysis / search / data.
    """

    # Keyword sets for classification
    _CHAT_KW = {
        "ciao", "salve", "buongiorno", "buonasera", "grazie", "come stai",
        "chi sei", "hello", "hi", "hey", "bravo", "ok", "perfetto",
        "arrivederci", "a dopo", "buona giornata", "come va",
    }
    _ANALYSIS_KW = {
        "analizza", "analisi", "value bet", "edge", "kelly", "scommessa",
        "match", "pronostico", "predizione", "consiglio", "consiglia",
        "migliore", "migliori", "giocata", "giocate", "valore", "quota",
        "quote", "spread", "totals", "over", "under", "previsione",
        "previsioni", "probabilita", "probabilità", "favorito",
    }
    _SEARCH_KW = {
        "cerca", "search", "news", "notizie", "notizia", "infortun",
        "ritir", "meteo", "weather", "injury", "injuries", "forma",
        "ultim", "aggiorna", "update", "rumor", "rumors",
    }

    def __init__(self, config_path="config/config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        agent_cfg = config["agent"]["openrouter"]
        self.api_key = os.getenv("OPENROUTER_API_KEY") or agent_cfg.get("api_key", "")
        self.model = agent_cfg["model"]
        self.system_prompt = agent_cfg["system_prompt"]
        self.max_history = agent_cfg.get("max_history", 10)
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.ctx = ctx

        # Conversation history for multi-turn dialogue
        self.history = []

        # Web research module (shared with news_adjustment)
        self.web_research = WebResearch()

    # ------------------------------------------------------------------
    # Query Classification
    # ------------------------------------------------------------------

    def _classify_query(self, query: str) -> str:
        """Classify query into: chat, analysis, search, data."""
        q = query.lower().strip()

        # Check exact chat greetings first (short messages)
        for kw in self._CHAT_KW:
            if q == kw or q.startswith(kw + " ") or q.endswith(" " + kw):
                return "chat"

        # Very short messages without analysis keywords = chat
        if len(q.split()) <= 2 and not any(kw in q for kw in self._ANALYSIS_KW):
            return "chat"

        # Search keywords
        for kw in self._SEARCH_KW:
            if kw in q:
                return "search"

        # Analysis keywords
        for kw in self._ANALYSIS_KW:
            if kw in q:
                return "analysis"

        # Default: if predictions exist, analysis; else chat
        return "analysis"

    # ------------------------------------------------------------------
    # Context builders
    # ------------------------------------------------------------------

    def _format_predictions_context(self, predictions: list) -> str:
        """Rich predictions context for analysis queries."""
        if not predictions:
            return "Nessun match disponibile al momento.\n"

        header = f"DATI PREDIZIONI ML ({len(predictions)} match):\n" + "=" * 50 + "\n\n"
        return header + "".join(_prediction_block(p) for p in predictions)

    def _build_search_context(self, query: str) -> str:
        """Web search context for search queries.
        Priority: Brave Search API > DuckDuckGo > Google News RSS.
        """
        results = []

        # Try to find player names in the query
        player_match = re.search(
            r'(?:news\s+(?:su|di|about)|cerca|search|notizie\s+(?:su|di))\s+(.+)',
            query.lower()
        )
        if player_match:
            search_term = player_match.group(1).strip()
        else:
            # Use the full query as search term
            search_term = query.strip()

        # 1. Google News RSS (headlines + snippets)
        news = self.web_research.search_player_news(search_term)
        if news:
            results.append(f"GOOGLE NEWS per '{search_term}':")
            for n in news[:5]:
                results.append(f"  - {n['title']} [{n.get('source', '?')}] ({n.get('date', '')})")
                if n.get("snippet"):
                    results.append(f"    >>> {n['snippet'][:300]}")

        # 2. DuckDuckGo (broader web results with snippets)
        ddg = self.web_research.search_web(f"{search_term} tennis")
        if ddg:
            results.append(f"\nWEB SEARCH per '{search_term}':")
            for d in ddg[:5]:
                results.append(f"  - {d['title']}")
                if d.get("snippet"):
                    results.append(f"    >>> {d['snippet'][:300]}")

        if not results:
            return "Nessuna news trovata per la ricerca.\n"

        return "\n".join(results) + "\n"

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def _user_message(self, query_type, query, predictions):
        """The prompt body for this query type: web results, full data, or nothing."""
        if query_type == "search":
            search_ctx = self._build_search_context(query)
            pred_summary = (f"\n({len(predictions)} match in portafoglio)"
                            if predictions else "")
            return f"RISULTATI WEB SEARCH:\n{search_ctx}{pred_summary}\n\nDOMANDA: {query}"
        if query_type == "analysis":
            return f"{self._format_predictions_context(predictions)}\nDOMANDA UTENTE: {query}"
        return query  # chat and anything unrecognised stay conversational

    def _request_with_retry(self, messages, attempts=3):
        """Assistant reply, retrying rate limits and timeouts; None once spent."""
        import time as _time

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps({"model": self.model, "messages": messages}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "Tennis Pro Terminal",
            },
            method="POST",
        )
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=60) as response:
                    raw = response.read().decode("utf-8").strip()
                    return json.loads(raw)["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code == 429 and not last:
                    _time.sleep((attempt + 1) * 5)
                    continue
                raise
            except Exception as e:
                if not last and "timed out" in str(e).lower():
                    _time.sleep(3)
                    continue
                raise
        return None

    def ask(self, query: str, predictions_path: str = "data/live/predictions.json") -> str:
        """Smart-routed query: classifies, injects appropriate context, calls LLM."""
        if not self.api_key or self.api_key.startswith("${") or self.api_key == "YOUR_OPENROUTER_API_KEY_HERE":
            return "AI Agent Offline: OpenRouter API Key non configurata. Aggiungi OPENROUTER_API_KEY nel file .env"

        try:
            query_type = self._classify_query(query)

            # Load predictions for analysis/search
            predictions = []
            if os.path.exists(predictions_path):
                try:
                    with open(predictions_path, "r") as f:
                        predictions = json.load(f)
                except ValueError:
                    predictions = []

            user_message = self._user_message(query_type, query, predictions)
            messages = ([{"role": "system", "content": self.system_prompt}]
                        + list(self.history[-self.max_history:])
                        + [{"role": "user", "content": user_message}])
            reply = self._request_with_retry(messages)
            if reply is None:
                return "LLM non disponibile dopo 3 tentativi. Riprova tra poco."
            self.history.append({"role": "user", "content": query})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            return f"Errore comunicazione AI: {str(e)}"

    def clear_history(self):
        """Reset conversation history."""
        self.history = []


if __name__ == "__main__":
    agent = AgentLLM()
    # Test classification
    tests = ["ciao", "analizza i match", "cerca news su Sinner", "grazie mille"]
    for t in tests:
        print(f"  '{t}' -> {agent._classify_query(t)}")
    print(agent.ask("Quali sono le migliori giocate?"))
