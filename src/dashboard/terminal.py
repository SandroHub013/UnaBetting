"""Real interactive terminals over WebSocket: native PTY <-> xterm.js.

/ws/term?shell=<whitelisted>   one PTY per connection; multiple connections =
multiple independent terminals. Full shell = arbitrary code execution BY DESIGN
(local personal tool, see spec — security section).

Protocol (client -> server, JSON):
  {"type":"input","data":"<keys>"}    {"type":"resize","cols":N,"rows":N}
Server -> client: raw text frames (terminal output).
"""
import asyncio
import json
import sys
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import config, security
from .pty_process import spawn_terminal

router = APIRouter()


def _terminal_command(shell: str, agent: str = "") -> str | list[str] | None:
    """Build a whitelisted terminal command without interpolating clone paths."""
    if agent:
        cmd = config.VIBE_AGENTS.get(agent)
        if not cmd:
            return None
        session = f"vibe-{agent}"
        if sys.platform == "win32":
            return [
                "wsl.exe", "--cd", str(config.PROJECT_ROOT.resolve()), "-e", "bash", "-lc",
                f"tmux new-session -A -s {session} {cmd}",
            ]
        return ["tmux", "new-session", "-A", "-s", session, cmd]

    return config.SHELLS.get(shell)


def _unsupported_detail(shell, agent):
    if agent:
        return (f"agente '{agent}' non in whitelist "
                f"(disponibili: {', '.join(config.VIBE_AGENTS)})")
    return (f"shell '{shell}' non supportata "
            f"(disponibili: {', '.join(config.SHELLS)})")


async def _open_pty(ws, cmdline):
    """Spawn the terminal, or report why it could not start and close the socket."""
    try:
        return spawn_terminal(cmdline, cwd=str(config.PROJECT_ROOT), dimensions=(30, 120))
    except Exception as e:
        # e.g. WSL not installed -> clear message, clean close
        await ws.send_text(f"\r\n[dashboard] impossibile avviare '{cmdline}': {e}\r\n")
        await ws.close()
        return None


async def _pty_to_ws(pty, ws, loop):
    """Forward terminal output until either side goes away."""
    while True:
        try:
            data = await loop.run_in_executor(None, pty.read)
        except (EOFError, OSError):
            break
        if not data:
            break
        try:
            await ws.send_text(data)
        except Exception:
            break
    with suppress(Exception):
        await ws.close()


def _apply_client_frame(pty, raw):
    """Resize or input; anything that is not JSON is a raw key frame."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        pty.write(raw)
        return
    if msg.get("type") == "resize":
        with suppress(Exception):
            pty.setwinsize(int(msg.get("rows", 30)), int(msg.get("cols", 120)))
    elif msg.get("type") == "input":
        pty.write(msg.get("data", ""))


@router.websocket("/ws/term")
async def ws_term(ws: WebSocket, shell: str = "", agent: str = ""):
    if not await security.authorize_websocket(ws):
        return
    await ws.accept()

    # Agent argv stays structured so clone paths with spaces remain intact.
    shell = shell or config.DEFAULT_SHELL
    cmdline = _terminal_command(shell, agent)
    if not cmdline:
        await ws.send_text(f"\r\n[dashboard] {_unsupported_detail(shell, agent)}\r\n")
        await ws.close()
        return

    pty = await _open_pty(ws, cmdline)
    if pty is None:
        return

    loop = asyncio.get_running_loop()
    reader = asyncio.create_task(_pty_to_ws(pty, ws, loop))
    try:
        while True:
            _apply_client_frame(pty, await ws.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(Exception):
            pty.terminate(force=True)
        reader.cancel()
        # awaited so the cancelled task is reaped instead of left pending
        with suppress(asyncio.CancelledError):
            await reader
