"""Smoke test: vibe terminal WS spawns the agent inside tmux on WSL."""
import asyncio
import json
import re
import subprocess

import websockets

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][0-9A-B]")


async def main():
    # use codex (light TUI) to validate the chain; same path for all agents
    uri = "ws://127.0.0.1:8765/ws/term?shell=wsl&agent=codex"
    out = ""
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "resize", "cols": 110, "rows": 30}))
        try:
            for _ in range(40):
                out += await asyncio.wait_for(ws.recv(), timeout=4)
                if len(out) > 1500:
                    break
        except asyncio.TimeoutError:
            pass
    clean = ANSI.sub("", out)
    print(f"bytes streamed: {len(out)}")
    print("tail:", repr(clean[-300:]))

    # tmux session must exist (and survive the closed websocket)
    r = subprocess.run(["wsl.exe", "-e", "bash", "-lc", "tmux ls"],
                       capture_output=True, text=True, timeout=30)
    print("tmux ls ->", r.stdout.strip() or r.stderr.strip())
    ok = "vibe-codex" in r.stdout
    print("session vibe-codex:", "OK" if ok else "MISSING")

    # cleanup: kill the test session so no agent is left running
    subprocess.run(["wsl.exe", "-e", "bash", "-lc", "tmux kill-session -t vibe-codex"],
                   capture_output=True, text=True, timeout=30)
    raise SystemExit(0 if (ok and len(out) > 0) else 1)

asyncio.run(main())
