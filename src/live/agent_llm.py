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
        self.ctx = ssl.create_default_context()

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

        context = f"DATI PREDIZIONI ML ({len(predictions)} match):\n"
        context += "=" * 50 + "\n\n"

        for p in predictions:
            f = p.get('forensics', {})
            low_conf = p.get('low_confidence', False)

            conf_tag = " [LOW CONFIDENCE]" if low_conf else ""
            context += f"MATCH: {p['match']}{conf_tag}\n"
            context += f"  H2H: P1 {p['prob_1']:.1%} @{p['odds_1']:.2f} | P2 {p['prob_2']:.1%} @{p['odds_2']:.2f}\n"
            context += f"  Edge: {p['edge']:+.1%} (lato P{p.get('value_side', '?')})\n"

            # Surface & tournament
            surface = p.get("surface", f.get("surface", "?"))
            tourney = f.get("tourney_name", "")
            if surface or tourney:
                context += f"  Superficie: {surface}"
                if tourney:
                    context += f" ({tourney})"
                context += "\n"

            # ELO
            context += f"  ELO: P1 {f.get('p1_elo', 'N/A')} (sup: {f.get('p1_surface_elo', 'N/A')}) | P2 {f.get('p2_elo', 'N/A')} (sup: {f.get('p2_surface_elo', 'N/A')})\n"

            # Form & H2H
            context += f"  Forma: P1 {f.get('p1_form', 'N/A')} | P2 {f.get('p2_form', 'N/A')}\n"
            context += f"  H2H: {f.get('p1_h2h', 0)} - {f.get('p2_h2h', 0)}\n"

            # Spread
            exp_diff = f.get('exp_game_diff', 0)
            mkt_spread = f.get('market_spread', 0)
            spread_edge = f.get('spread_edge', '')
            spread_tag = f" -> VALORE {spread_edge}" if spread_edge else ""
            context += f"  Spread: ML {exp_diff:+.1f} vs Linea {mkt_spread:+.1f}{spread_tag}\n"

            # Totals
            exp_total = f.get('exp_total_games', 0)
            mkt_total = f.get('market_total', 0)
            totals_edge = f.get('totals_edge', '')
            totals_tag = f" -> VALORE {totals_edge}" if totals_edge else ""
            context += f"  Totals: ML {exp_total:.1f} vs Linea {mkt_total:.1f}{totals_tag}\n"

            # News adjustment info
            adj = p.get("news_adjustment")
            if adj and adj.get("applied"):
                raw_p1 = p.get("raw_prob_1", p["prob_1"])
                context += f"  NEWS: {adj['reason']} (adj: {adj['effective']:+.3f}, conf: {adj['confidence']:.0%})\n"
                context += f"  Prob pre-news: {raw_p1:.1%} -> post-news: {p['prob_1']:.1%}\n"

            context += "\n"

        return context

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
                except (json.JSONDecodeError, ValueError):
                    predictions = []

            # Build user message based on query type
            if query_type == "chat":
                # No data context — just conversational
                user_message = query
            elif query_type == "search":
                # Web search context + predictions summary
                search_ctx = self._build_search_context(query)
                pred_summary = f"\n({len(predictions)} match in portafoglio)" if predictions else ""
                user_message = f"RISULTATI WEB SEARCH:\n{search_ctx}{pred_summary}\n\nDOMANDA: {query}"
            elif query_type == "analysis":
                # Full predictions context
                context = self._format_predictions_context(predictions)
                user_message = f"{context}\nDOMANDA UTENTE: {query}"
            else:
                user_message = query

            # Build messages: system + history + current
            messages = [{"role": "system", "content": self.system_prompt}]
            for msg in self.history[-self.max_history:]:
                messages.append(msg)
            messages.append({"role": "user", "content": user_message})

            data = {
                "model": self.model,
                "messages": messages,
            }

            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(data).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-Title": "Tennis Pro Terminal",
                },
                method="POST",
            )

            # Retry with backoff for rate limits
            import time as _time
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, context=self.ctx, timeout=60) as response:
                        raw = response.read().decode("utf-8").strip()
                        result = json.loads(raw)
                        assistant_reply = result["choices"][0]["message"]["content"]

                        self.history.append({"role": "user", "content": query})
                        self.history.append({"role": "assistant", "content": assistant_reply})
                        return assistant_reply
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < 2:
                        wait = (attempt + 1) * 5
                        _time.sleep(wait)
                        continue
                    raise
                except Exception as e:
                    if attempt < 2 and "timed out" in str(e).lower():
                        _time.sleep(3)
                        continue
                    raise

            return "LLM non disponibile dopo 3 tentativi. Riprova tra poco."

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
