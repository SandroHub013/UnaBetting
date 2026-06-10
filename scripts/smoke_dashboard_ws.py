"""Smoke test WS endpoints of the running dashboard: terminal + runner."""
import asyncio
import json
import re

import websockets

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


async def test_terminal():
    uri = "ws://127.0.0.1:8765/ws/term?shell=powershell"
    async with websockets.connect(uri) as ws:
        # wait for the prompt to appear (PS startup banner can be slow)
        out = ""
        try:
            for _ in range(30):
                out += await asyncio.wait_for(ws.recv(), timeout=4)
                if ">" in ANSI.sub("", out):
                    break
        except asyncio.TimeoutError:
            pass
        assert out, "no terminal output received"
        await ws.send(json.dumps({"type": "input", "data": "Write-Output ('MC_'+'TERM_OK')\r"}))
        echoed = ""
        try:
            for _ in range(30):
                echoed += await asyncio.wait_for(ws.recv(), timeout=4)
                if "MC_TERM_OK" in ANSI.sub("", echoed):
                    break
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"type": "resize", "cols": 100, "rows": 25}))
        # the typed command never contains the literal marker ('MC_'+'TERM_OK'),
        # so seeing MC_TERM_OK in clean output proves the shell EXECUTED it
        ok = "MC_TERM_OK" in ANSI.sub("", echoed)
        print(f"terminal powershell: {'OK' if ok else 'FAIL'} ({len(out)+len(echoed)} bytes streamed)")
        if not ok:
            clean = ANSI.sub("", out + echoed)
            print("---- tail of cleaned output ----")
            print(repr(clean[-400:]))
        return ok


async def test_runner_reject():
    async with websockets.connect("ws://127.0.0.1:8765/ws/run") as ws:
        await ws.send(json.dumps({"cmd": "format c:"}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        ok = msg.get("type") == "error" and "whitelist" in msg.get("detail", "")
        print(f"runner whitelist reject: {'OK' if ok else 'FAIL'} -> {msg}")
        return ok


async def main():
    r1 = await test_terminal()
    r2 = await test_runner_reject()
    raise SystemExit(0 if (r1 and r2) else 1)

asyncio.run(main())
