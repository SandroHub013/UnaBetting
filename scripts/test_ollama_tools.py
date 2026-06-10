"""Test: il modello locale sa fare tool calling per l'agente dell'app?"""
import json
import time
import urllib.request

TOOLS = [{
    "type": "function",
    "function": {
        "name": "scan_match_live",
        "description": "Scarica le quote fresche dei match di tennis di oggi e fa girare il modello ML. Usalo quando l'utente chiede i match di oggi, le quote o i segnali aggiornati.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}, {
    "type": "function",
    "function": {
        "name": "leggi_metriche_modello",
        "description": "Legge accuracy, log loss e ROC del modello ML corrente.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}]


def ask(model, question):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Sei l'assistente di Mission Control, app di analisi tennis. Usa i tool quando servono dati live."},
            {"role": "user", "content": question},
        ],
        "tools": TOOLS,
        "stream": False,
    }
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0
    msg = resp.get("message", {})
    calls = msg.get("tool_calls") or []
    ev = resp.get("eval_count", 0)
    ed = resp.get("eval_duration", 1) / 1e9
    print(f"\n[{model}] {dt:.1f}s totali, {ev/ed:.1f} tok/s")
    if calls:
        print("  TOOL CALLS:", [c["function"]["name"] for c in calls])
    else:
        print("  nessun tool call. Risposta:", (msg.get("content") or "")[:200])


for model in ["qwen3.5:9b", "qwen3.5:4b"]:
    try:
        ask(model, "quali sono i match di oggi?")
        ask(model, "com'e' messo il modello? accuracy?")
    except Exception as e:
        print(f"\n[{model}] ERRORE: {e}")
