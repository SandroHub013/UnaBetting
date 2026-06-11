"""Real interactive terminals over WebSocket: pywinpty (ConPTY) <-> xterm.js.

/ws/term?shell=powershell|wsl   one PTY per connection; multiple connections =
multiple independent terminals. Full shell = arbitrary code execution BY DESIGN
(local personal tool, see spec — security section).

Protocol (client -> server, JSON):
  {"type":"input","data":"<keys>"}    {"type":"resize","cols":N,"rows":N}
Server -> client: raw text frames (terminal output).
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import config

router = APIRouter()


@router.websocket("/ws/term")
async def ws_term(ws: WebSocket, shell: str = "powershell", agent: str = ""):
    token = config.auth_token()
    if token and ws.query_params.get("token") != token:
        await ws.close(code=4401)
        return
    await ws.accept()

    if agent:
        # vibe coding: whitelisted agent inside a persistent tmux session on WSL.
        # argv as a LIST: a quoted cmdline string gets mangled by spawn parsing.
        cmd = config.VIBE_AGENTS.get(agent)
        if not cmd:
            await ws.send_text(f"\r\n[dashboard] agente '{agent}' non in whitelist "
                               f"(disponibili: {', '.join(config.VIBE_AGENTS)})\r\n")
            await ws.close()
            return
        session = f"vibe-{agent}"
        wsl_dir = config.WSL_PROJECT_DIR.replace("'", "'\\''")
        cmdline = ["wsl.exe", "-e", "bash", "-lc",
                   f"cd '{wsl_dir}' 2>/dev/null; tmux new-session -A -s {session} {cmd}"]
    else:
        cmdline = config.SHELLS.get(shell)
        if not cmdline:
            await ws.send_text(f"\r\n[dashboard] shell '{shell}' non supportata "
                               f"(disponibili: {', '.join(config.SHELLS)})\r\n")
            await ws.close()
            return

    try:
        from winpty import PtyProcess
        pty = PtyProcess.spawn(cmdline, cwd=str(config.PROJECT_ROOT), dimensions=(30, 120))
    except Exception as e:
        # e.g. WSL not installed -> clear message, clean close
        await ws.send_text(f"\r\n[dashboard] impossibile avviare '{cmdline}': {e}\r\n")
        await ws.close()
        return

    loop = asyncio.get_running_loop()

    async def pty_to_ws():
        while True:
            try:
                data = await loop.run_in_executor(None, pty.read)
            except (EOFError, ConnectionError, OSError):
                break
            if not data:
                break
            try:
                await ws.send_text(data)
            except Exception:
                break
        try:
            await ws.close()
        except Exception:
            pass

    reader = asyncio.create_task(pty_to_ws())
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                pty.write(raw)  # tolerate raw key frames
                continue
            if msg.get("type") == "resize":
                try:
                    pty.setwinsize(int(msg.get("rows", 30)), int(msg.get("cols", 120)))
                except Exception:
                    pass
            elif msg.get("type") == "input":
                pty.write(msg.get("data", ""))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            pty.terminate(force=True)
        except Exception:
            pass
        reader.cancel()
