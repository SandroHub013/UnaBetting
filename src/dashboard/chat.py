"""In-app chat agent: local Ollama (qwen3.5:9b) + whitelisted tools.

/ws/chat protocol — client sends {"text": "..."}; server emits:
  {"type":"tool","name":...,"status":"start"|"done"}   tool activity
  {"type":"reply","text":...}                          final answer
  {"type":"refresh"}                                   data changed, re-render panels
  {"type":"error","detail":...}
The model never executes anything directly: it can only pick from the tool
functions below (same trust model as the pipeline whitelist).
"""
import asyncio
import json
import urllib.request
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import config, security

router = APIRouter()

SYSTEM_PROMPT = """You are UnaBettingOS, the agentic memory and intelligence core of UnaBetting (a tennis analytics app).
Reply in the user's language, concise and concrete. Use the tools to get real data: NEVER invent numbers, odds or matches.
You have persistent memory: use save_memory to record important facts/decisions the user tells you, and recall_memory / search_knowledge to retrieve knowledge from the project's Obsidian vault and the knowledge graph (graphify).
Honest project context: the ML model has ~67.4% accuracy on the 2025+ test set and NO proven predictive edge — the honest backtest loses money to the bookmaker margin. Never promise winnings; remind the user of this if they draw risky conclusions.
scan_match_live consumes paid API credits: use it ONLY if the user explicitly asks to update/scan; for "today's matches" use get_today_matches.
When reporting matches: ALWAYS state the snapshot time and how old it is (ore_fa), name the tournament(s) (tornei) and tour, and mark matches already started (iniziato=true) — do not present started/past matches as upcoming. If nota_copertura is set, relay it: the odds feed only carries the events the-odds-api lists as active right now (often just one tournament/tour; ATP can be entirely absent). Never claim a tour is missing because of our filtering when it's the feed's coverage.
Odds: we only consider pinnacle (sharp reference) + williamhill, sport888, marathonbet, betfair (ADM-legal venues in Italy)."""

MAX_TOOL_ROUNDS = 4


# ---------------- tools ----------------

def t_get_today_matches():
    """Matches in the latest odds snapshot, with best legal prices.

    Honest about coverage: returns the snapshot age, the tournament(s) actually in
    the odds feed, the tour (ATP/WTA), and flags matches that have already started —
    the feed only carries events the-odds-api lists as active (often just a subset;
    ATP may be entirely absent on a given day)."""
    import pandas as pd
    from datetime import timezone
    if not config.ODDS_HISTORY.exists():
        return {"matches": [], "note": "nessuno snapshot quote su disco"}
    df = pd.read_csv(config.ODDS_HISTORY)
    if df.empty:
        return {"matches": [], "note": "snapshot vuoto"}
    last_ts = df["snapshot_ts"].max()
    snap = df[(df["snapshot_ts"] == last_ts) & (df["market"] == "h2h") &
              df["bookmaker"].isin(config.ALLOWED_BOOKMAKERS)]
    now = datetime.now(timezone.utc)

    def _started(ct):
        try:
            t = datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return t < now
        except Exception:
            return None

    out = []
    for (p1, p2), g in snap.groupby(["p1", "p2"]):
        ct = g["commence_time"].iloc[0]
        out.append({"match": f"{p1} vs {p2}",
                    "best_quota_p1": round(float(g["price_1"].max()), 2),
                    "best_quota_p2": round(float(g["price_2"].max()), 2),
                    "books": int(g["bookmaker"].nunique()),
                    "inizio": str(ct), "iniziato": _started(ct)})
    out.sort(key=lambda m: (m["iniziato"] is True, m["inizio"]))

    keys = sorted(snap["sport_key"].dropna().unique()) if "sport_key" in snap else []
    tornei = [k.replace("tennis_", "").replace("_", " ").title() for k in keys]
    tours = sorted({"ATP" if "_atp_" in k else "WTA" if "_wta_" in k else "?" for k in keys})
    age_h = (datetime.now() - datetime.fromisoformat(last_ts)).total_seconds() / 3600
    note = None
    if tours and tours == ["WTA"]:
        note = ("Il feed quote (the-odds-api) ha SOLO eventi WTA attivi ora — nessun "
                "ATP disponibile. Non è un filtro nostro: l'API non sta servendo tornei ATP.")
    elif tours == ["ATP"]:
        note = "Il feed quote ha solo eventi ATP attivi ora."
    return {"snapshot": last_ts, "ore_fa": round(age_h, 1),
            "tornei": tornei, "tour": tours, "n_match": len(out),
            "nota_copertura": note, "matches": out}


def t_get_signals(limit: int = 10):
    """Latest model decisions/signals from the DB."""
    from .data_api import decisions
    rows = decisions(limit=limit)
    if not isinstance(rows, list):
        return {"error": "DB non leggibile"}
    return [{"quando": r["timestamp"], "match": r["match_str"], "edge": r["edge"],
             "side": r["value_side"], "kelly": r["kelly_fraction"],
             "low_confidence": bool(r["low_confidence"])} for r in rows]


def t_get_model_metrics():
    """Current honest model metrics."""
    from .data_api import model
    return model()


def t_get_bankroll():
    """Bankroll / bets / ROI overview."""
    from .data_api import overview
    return overview()


async def t_scan_match_live(ws=None):
    """Run the full live scan (fresh odds + inference). SLOW (minutes), paid credits."""
    proc = await asyncio.create_subprocess_exec(
        *config.COMMAND_WHITELIST["scan"], cwd=str(config.PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "scan oltre i 15 minuti, interrotto"}
    tail = out.decode("utf-8", errors="replace").strip().splitlines()[-12:]
    if ws is not None:
        try:
            await ws.send_text(json.dumps({"type": "refresh"}))
        except Exception:
            pass
    return {"exit": proc.returncode, "output": tail}


MEMORY_FILE = config.PROJECT_ROOT / "docs" / "obsidian" / "UnaBettingOS_Memoria.md"


def t_search_knowledge(query: str = ""):
    """Keyword search across the Obsidian vault + key project docs."""
    if not query.strip():
        return {"error": "query vuota"}
    terms = [t.lower() for t in query.split() if len(t) > 2]
    sources = list((config.PROJECT_ROOT / "docs" / "obsidian").glob("*.md")) + [
        config.PROJECT_ROOT / "EXPERIMENTS.md",
        config.PROJECT_ROOT / "DATA_SOURCES.md",
        config.PROJECT_ROOT / "docs" / "ALPHA_FINDINGS.md",
        config.PROJECT_ROOT / "docs" / "PROJECT_EVALUATION.md",
    ]
    hits = []
    for path in sources:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for para in text.split("\n\n"):
            low = para.lower()
            score = sum(1 for t in terms if t in low)
            if score:
                hits.append({"file": path.name, "score": score,
                             "excerpt": para.strip()[:500]})
    hits.sort(key=lambda h: -h["score"])
    return {"query": query, "results": hits[:6]} if hits else \
           {"query": query, "results": [], "note": "nessun risultato nel vault"}


def t_query_graph(term: str = ""):
    """Look up a concept in the graphify knowledge graph: node + neighbours."""
    gpath = config.PROJECT_ROOT / "graphify-out" / "graph.json"
    if not gpath.exists():
        return {"error": "graph.json non trovato — esegui graphify"}
    g = json.loads(gpath.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g.get("nodes", [])}
    tl = term.lower()
    matches = [n for n in g.get("nodes", []) if tl in str(n.get("label", "")).lower()][:3]
    if not matches:
        return {"term": term, "results": [], "note": "nessun nodo corrispondente"}
    out = []
    links = g.get("links", [])
    for m in matches:
        neigh = []
        for e in links:
            src = e["source"] if isinstance(e["source"], str) else e["source"].get("id")
            tgt = e["target"] if isinstance(e["target"], str) else e["target"].get("id")
            if src == m["id"] and tgt in nodes:
                neigh.append({"to": nodes[tgt].get("label"), "rel": e.get("relation")})
            elif tgt == m["id"] and src in nodes:
                neigh.append({"from": nodes[src].get("label"), "rel": e.get("relation")})
        out.append({"node": m.get("label"), "file": m.get("source_file"),
                    "connections": neigh[:12]})
    return {"term": term, "results": out}


def t_browse_web(url: str = ""):
    """Fetch a web page and return its readable text + links (agentic browsing)."""
    if not url.strip():
        return {"error": "url vuoto"}
    from .data_api import browse
    res = browse(url)
    if hasattr(res, "body"):  # JSONResponse error
        return {"error": "fetch fallito", "url": url}
    return {"url": res["url"], "title": res["title"],
            "text": res["text"][:6000], "links": res["links"][:25]}


def t_save_memory(note: str = ""):
    """Append a fact/decision to the persistent UnaBettingOS memory (in the vault)."""
    if not note.strip():
        return {"error": "nota vuota"}
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(
            "---\ntags:\n  - unabettingos\n  - memoria\n---\n\n"
            "# UnaBettingOS — Memoria agentica\n\nNote salvate dall'agente in chat.\n",
            encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n- **{stamp}** — {note.strip()}")
    return {"saved": True, "file": str(MEMORY_FILE.name)}


def t_recall_memory():
    """Read the persistent UnaBettingOS memory notes."""
    if not MEMORY_FILE.exists():
        return {"notes": [], "note": "memoria ancora vuota"}
    lines = [l[2:] for l in MEMORY_FILE.read_text(encoding="utf-8").splitlines()
             if l.startswith("- ")]
    return {"notes": lines[-30:]}


TOOLS = {
    "get_today_matches": {
        "fn": t_get_today_matches, "is_async": False,
        "desc": "Elenca i match di tennis nello snapshot quote più recente, con le migliori quote legali per lato. Veloce, non consuma crediti.",
    },
    "get_signals": {
        "fn": t_get_signals, "is_async": False,
        "desc": "Ultime decisioni/segnali del modello ML dal database (edge, side, kelly).",
        "params": {"limit": {"type": "integer", "description": "quante decisioni (default 10)"}},
    },
    "get_model_metrics": {
        "fn": t_get_model_metrics, "is_async": False,
        "desc": "Metriche oneste correnti del modello ML (accuracy, log loss, ROC) e storico training.",
    },
    "get_bankroll": {
        "fn": t_get_bankroll, "is_async": False,
        "desc": "Stato bankroll, bet aperte/chiuse, ROI, win rate.",
    },
    "scan_match_live": {
        "fn": t_scan_match_live, "is_async": True, "pass_ws": True,
        "desc": "Scarica quote FRESCHE e fa girare modello+news (minuti, consuma crediti API a pagamento). Solo su richiesta esplicita di aggiornamento.",
    },
    "search_knowledge": {
        "fn": t_search_knowledge, "is_async": False,
        "desc": "Cerca nel vault Obsidian e nei documenti del progetto (metriche oneste, esperimenti, alpha findings, fonti dati). Usalo per domande su storia, decisioni e conoscenza del progetto.",
        "params": {"query": {"type": "string", "description": "parole chiave da cercare"}},
    },
    "query_graph": {
        "fn": t_query_graph, "is_async": False,
        "desc": "Interroga il knowledge graph del codice (graphify): trova un concetto/modulo e le sue connessioni.",
        "params": {"term": {"type": "string", "description": "nome del concetto/funzione/modulo"}},
    },
    "save_memory": {
        "fn": t_save_memory, "is_async": False,
        "desc": "Salva una nota/fatto/decisione nella memoria persistente di UnaBettingOS (nel vault Obsidian). Usalo quando l'utente ti dice qualcosa da ricordare.",
        "params": {"note": {"type": "string", "description": "la nota da ricordare"}},
    },
    "recall_memory": {
        "fn": t_recall_memory, "is_async": False,
        "desc": "Rileggi le note salvate nella memoria persistente di UnaBettingOS.",
    },
    "browse_web": {
        "fn": t_browse_web, "is_async": False,
        "desc": "Apri una pagina web e leggine il contenuto (testo + link). Usalo per news tennis, risultati, info su giocatori o qualunque URL l'utente chieda.",
        "params": {"url": {"type": "string", "description": "URL o dominio da aprire"}},
    },
}


def _tool_defs():
    out = []
    for name, t in TOOLS.items():
        props = t.get("params", {})
        out.append({"type": "function", "function": {
            "name": name, "description": t["desc"],
            "parameters": {"type": "object", "properties": props, "required": []}}})
    return out


def _ollama_call(messages):
    payload = {"model": config.CHAT_MODEL, "messages": messages,
               "tools": _tool_defs(), "stream": False,
               "keep_alive": config.CHAT_KEEP_ALIVE,
               "options": {"temperature": 0.2}}
    req = urllib.request.Request(f"{config.OLLAMA_URL}/api/chat",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    if not await security.authorize_websocket(ws):
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        while True:
            raw = await ws.receive_text()
            try:
                text = json.loads(raw).get("text", "").strip()
            except json.JSONDecodeError:
                text = raw.strip()
            if not text:
                continue
            messages.append({"role": "user", "content": text})

            tool_data = {}   # raw results per tool -> frontend templates
            try:
                for _ in range(MAX_TOOL_ROUNDS):
                    resp = await loop.run_in_executor(None, _ollama_call, messages)
                    msg = resp.get("message", {})
                    calls = msg.get("tool_calls") or []
                    if not calls:
                        reply = (msg.get("content") or "").strip()
                        messages.append({"role": "assistant", "content": reply})
                        await ws.send_text(json.dumps(
                            {"type": "reply", "text": reply, "data": tool_data},
                            ensure_ascii=False, default=str))
                        break
                    messages.append(msg)
                    for call in calls:
                        name = call.get("function", {}).get("name", "")
                        args = call.get("function", {}).get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        tool = TOOLS.get(name)
                        await ws.send_text(json.dumps({"type": "tool", "name": name, "status": "start"}))
                        if tool is None:
                            result = {"error": f"tool sconosciuto: {name}"}
                        else:
                            try:
                                if tool.get("is_async"):
                                    kwargs = {"ws": ws} if tool.get("pass_ws") else {}
                                    result = await tool["fn"](**kwargs)
                                else:
                                    result = await loop.run_in_executor(
                                        None, lambda: tool["fn"](**args))
                            except Exception as e:
                                result = {"error": str(e)}
                        await ws.send_text(json.dumps({"type": "tool", "name": name, "status": "done"}))
                        tool_data[name] = result
                        messages.append({"role": "tool", "tool_name": name,
                                         "content": json.dumps(result, ensure_ascii=False, default=str)})
                else:
                    await ws.send_text(json.dumps(
                        {"type": "reply", "text": "(troppi giri di tool — riformula la domanda)"}))
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "detail": str(e)}))
    except WebSocketDisconnect:
        pass
