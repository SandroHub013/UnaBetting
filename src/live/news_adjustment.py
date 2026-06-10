"""
News-based Probability Adjustment Engine.
Scrapes news, sends to LLM for structured adjustment factors,
applies capped adjustments to ML probabilities.
"""
import os
import json
import urllib.request
import urllib.error
import ssl
import yaml
from dotenv import load_dotenv

load_dotenv()

from src.live.web_research import WebResearch

MAX_ADJUSTMENT = 0.15   # +-15 percentage points
MIN_PROB = 0.05
MAX_PROB = 0.95

ADJUSTMENT_SYSTEM_PROMPT = """\
Sei un analista che valuta l'impatto di notizie recenti sulle probabilita' \
di un modello ML per tennis.

Per ogni match ti fornisco: probabilita' ML, odds, e notizie trovate online.
Rispondi SOLO con un JSON array valido, senza altro testo.

Per ogni match rispondi con:
{
  "match": "stringa esatta del match",
  "adjustment": float tra -0.15 e +0.15 (positivo = favorisce P1, negativo = favorisce P2),
  "confidence": float 0.0-1.0,
  "reason": "motivazione breve, max 20 parole"
}

Linee guida per l'adjustment:
- Infortunio confermato a un giocatore: -0.08 a -0.15 per quel giocatore
- Primo match dopo >60 giorni inattivita': -0.03 a -0.08
- Ritiro annunciato pre-match: -0.15
- Forma eccellente recente non catturata dal modello: +0.03 a +0.08
- Condizioni meteo sfavorevoli a uno specifico giocatore: -0.02 a -0.05
- Nessuna news rilevante: adjustment 0.0, confidence 1.0
- Se non sei sicuro, usa confidence bassa (0.3-0.5) e adjustment contenuto

IMPORTANTE: il segno dell'adjustment e' relativo a P1.
+0.08 = P1 favorito di 8pp in piu' rispetto al modello.
-0.08 = P2 favorito di 8pp in piu' rispetto al modello.\
"""


def _build_match_context(predictions: list, news_data: dict) -> str:
    """Build match-by-match context for the LLM."""
    lines = []
    for p in predictions:
        match_str = p["match"]
        news = news_data.get(match_str, {})
        p1_news = news.get("p1_news", [])
        p2_news = news.get("p2_news", [])
        tourney_news = news.get("tourney_news", [])

        lines.append(f"MATCH: {match_str}")
        lines.append(f"  ML Prob: P1={p['prob_1']:.1%}  P2={p['prob_2']:.1%}")
        lines.append(f"  Odds: P1={p['odds_1']:.2f}  P2={p['odds_2']:.2f}")
        lines.append(f"  Surface: {p.get('surface', '?')}")

        if p1_news:
            lines.append("  NEWS P1:")
            for n in p1_news[:3]:
                lines.append(f"    - {n['title']}")
                if n.get("snippet"):
                    lines.append(f"      Content: {n['snippet'][:250]}")
        if p2_news:
            lines.append("  NEWS P2:")
            for n in p2_news[:3]:
                lines.append(f"    - {n['title']}")
                if n.get("snippet"):
                    lines.append(f"      Content: {n['snippet'][:250]}")
        if tourney_news and predictions.index(p) == 0:
            lines.append("  NEWS TORNEO:")
            for n in tourney_news[:2]:
                lines.append(f"    - {n['title']}")
                if n.get("snippet"):
                    lines.append(f"      Content: {n['snippet'][:200]}")

        if not p1_news and not p2_news:
            lines.append("  NEWS: nessuna trovata")
        lines.append("")

    return "\n".join(lines)


def _call_llm_for_adjustments(context: str) -> list[dict]:
    """Send context to OpenRouter LLM and parse structured JSON adjustments."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("${"):
        return []

    # Load news adjustment model from config (separate from agent model)
    try:
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        model = config.get("news_adjustment", {}).get(
            "model", config["agent"]["openrouter"]["model"]
        )
    except Exception:
        model = "meta-llama/llama-3.1-8b-instruct:free"

    # Fallback chain: if primary model fails, try alternatives
    model_fallbacks = [
        model,
        "z-ai/glm-5.1",
        "meta-llama/llama-3.1-8b-instruct:free",
    ]
    # Deduplicate while preserving order
    seen = set()
    model_chain = []
    for m in model_fallbacks:
        if m not in seen:
            seen.add(m)
            model_chain.append(m)

    messages = [
        {"role": "system", "content": ADJUSTMENT_SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    ctx = ssl.create_default_context()
    import time as _time
    import re as _re

    for model_name in model_chain:
        # Build fresh request for each attempt (urllib consumes data on read)
        payload = json.dumps({"model": model_name, "messages": messages}).encode("utf-8")

        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-Title": "Tennis Pro Terminal - News Adjustment",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, context=ctx, timeout=90) as resp:
                    raw = resp.read().decode("utf-8").strip()
                    result = json.loads(raw)
                    content = result["choices"][0]["message"]["content"].strip()

                    # Extract JSON from response (handle markdown code blocks)
                    if "```" in content:
                        m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
                        if m:
                            content = m.group(1).strip()

                    adjustments = json.loads(content)
                    if isinstance(adjustments, list):
                        return adjustments
                    return []
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                if e.code == 429 and attempt < 1:
                    wait = 5
                    print(f"  [News Adj] Rate limited (429) on {model_name}. Retry in {wait}s...")
                    _time.sleep(wait)
                    continue
                print(f"  [News Adj] {model_name} failed: HTTP {e.code} {body[:100]}")
                break  # Try next model
            except Exception as e:
                if attempt < 1 and "timed out" in str(e).lower():
                    print(f"  [News Adj] Timeout on {model_name}. Retrying...")
                    _time.sleep(3)
                    continue
                print(f"  [News Adj] {model_name} failed: {e}")
                break  # Try next model

    print("  [News Adj] All models failed. Returning no adjustments.")
    return []


def _apply_adjustments(predictions: list, adjustments: list) -> list:
    """Apply LLM adjustments to predictions with safety caps."""
    # Build lookup by match string
    adj_map = {}
    for a in adjustments:
        match_key = a.get("match", "")
        if match_key:
            adj_map[match_key] = a

    for p in predictions:
        match_str = p["match"]
        adj = adj_map.get(match_str)

        # Save raw probabilities
        p["raw_prob_1"] = p["prob_1"]
        p["raw_prob_2"] = p["prob_2"]

        if not adj:
            p["news_adjustment"] = None
            continue

        raw_adj = float(adj.get("adjustment", 0.0))
        confidence = max(0.0, min(1.0, float(adj.get("confidence", 0.0))))
        reason = str(adj.get("reason", ""))

        # Weighted adjustment
        effective_adj = raw_adj * confidence

        # Cap
        effective_adj = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, effective_adj))

        if abs(effective_adj) < 0.005:
            # Too small to matter
            p["news_adjustment"] = {
                "applied": False,
                "raw": raw_adj,
                "effective": 0.0,
                "confidence": confidence,
                "reason": reason,
            }
            continue

        # Apply symmetrically
        new_p1 = p["prob_1"] + effective_adj
        new_p2 = 1.0 - new_p1

        # Clamp
        new_p1 = max(MIN_PROB, min(MAX_PROB, new_p1))
        new_p2 = 1.0 - new_p1

        p["prob_1"] = new_p1
        p["prob_2"] = new_p2

        # Recalculate edge
        edge_1 = (p["odds_1"] * new_p1) - 1
        edge_2 = (p["odds_2"] * new_p2) - 1
        if edge_1 > edge_2:
            p["edge"] = edge_1
            p["value_side"] = 1
        else:
            p["edge"] = edge_2
            p["value_side"] = 2

        p["news_adjustment"] = {
            "applied": True,
            "raw": raw_adj,
            "effective": round(effective_adj, 4),
            "confidence": confidence,
            "reason": reason,
        }

    return predictions


def run_news_adjustment(predictions: list) -> list:
    """Main entry point: scrape news, get LLM adjustments, apply to predictions.

    Graceful fallback: if anything fails, returns predictions unchanged.
    """
    if not predictions:
        return predictions

    print("  [News] Fetching news for probability adjustment...")
    try:
        wr = WebResearch()
        news_data = wr.fetch_all_news_for_matches(predictions)

        # Check if we found any news at all
        has_news = any(
            data.get("p1_news") or data.get("p2_news")
            for data in news_data.values()
        )

        if not has_news:
            print("  [News] No relevant news found. Probabilities unchanged.")
            for p in predictions:
                p["raw_prob_1"] = p["prob_1"]
                p["raw_prob_2"] = p["prob_2"]
                p["news_adjustment"] = None
            return predictions

        # Build context and call LLM
        context = _build_match_context(predictions, news_data)
        print(f"  [News] Sending {len(predictions)} matches to LLM for adjustment analysis...")
        adjustments = _call_llm_for_adjustments(context)
        print(f"  [News] Received {len(adjustments)} adjustment responses.")

        # Apply
        predictions = _apply_adjustments(predictions, adjustments)

        adjusted_count = sum(
            1 for p in predictions
            if p.get("news_adjustment") and p["news_adjustment"].get("applied")
        )
        print(f"  [News] Adjustment complete: {adjusted_count}/{len(predictions)} matches adjusted.")

    except Exception as e:
        print(f"  [News] WARNING: Adjustment failed (fallback): {e}")
        for p in predictions:
            p.setdefault("raw_prob_1", p["prob_1"])
            p.setdefault("raw_prob_2", p["prob_2"])
            p.setdefault("news_adjustment", None)

    return predictions


if __name__ == "__main__":
    # Test with existing predictions
    import json
    from pathlib import Path

    pred_path = Path(__file__).parent.parent.parent / "data" / "live" / "predictions.json"
    if pred_path.exists():
        with open(pred_path) as f:
            preds = json.load(f)
        preds = run_news_adjustment(preds[:3])  # Test with first 3
        for p in preds:
            adj = p.get("news_adjustment")
            status = f"adj={adj['effective']:+.3f} ({adj['reason']})" if adj and adj.get("applied") else "no change"
            print(f"  {p['match']}: {p['raw_prob_1']:.1%} -> {p['prob_1']:.1%} [{status}]")
