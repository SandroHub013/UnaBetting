"""Smoke test /ws/chat: question in Italian -> tool call -> grounded answer."""
import asyncio
import json

import websockets


async def main():
    async with websockets.connect("ws://127.0.0.1:8765/ws/chat") as ws:
        await ws.send(json.dumps({"text": "com'e' messo il modello? dammi accuracy e log loss"}))
        tools, reply = [], None
        for _ in range(40):
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=240))
            except asyncio.TimeoutError:
                break
            if m["type"] == "tool":
                if m["status"] == "start":
                    tools.append(m["name"])
                print("tool:", m["name"], m["status"])
            elif m["type"] == "reply":
                reply = m["text"]
                print("reply:", reply[:400])
                break
            elif m["type"] == "error":
                print("ERROR:", m["detail"])
                break
        ok = reply is not None and "get_model_metrics" in tools and ("66" in reply or "0.6" in reply)
        print("\nRESULT:", "OK" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)

asyncio.run(main())
