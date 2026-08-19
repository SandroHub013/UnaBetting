"""Smoke test: vibe terminal WS spawns the agent inside tmux on WSL."""
import asyncio
import json
import re

import websockets

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][0-9A-B]")


async def wsl(cmd):
    """Run a bash command inside WSL without blocking the event loop."""
    proc = await asyncio.create_subprocess_exec(
        "wsl.exe", "-e", "bash", "-lc", cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    return stdout.decode(errors="replace"), stderr.decode(errors="replace")


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
    stdout, stderr = await wsl("tmux ls")
    print("tmux ls ->", stdout.strip() or stderr.strip())
    ok = "vibe-codex" in stdout
    print("session vibe-codex:", "OK" if ok else "MISSING")

    # cleanup: kill the test session so no agent is left running
    await wsl("tmux kill-session -t vibe-codex")
    raise SystemExit(0 if (ok and len(out) > 0) else 1)

asyncio.run(main())
