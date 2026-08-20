"""Pipeline runner WebSocket: launches whitelisted commands only, streams output.

Protocol (client -> server, JSON text frames):
  {"cmd": "<whitelist-name>"}   start a command (one at a time per connection)
  {"type": "stop"}              terminate the running command
Server -> client:
  {"type":"start","cmd":...} {"type":"line","stream":"out","text":...}
  {"type":"exit","code":N}   {"type":"error","detail":...}
"""
import asyncio
import json
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import config, security

router = APIRouter()


async def _stream(proc, ws):
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        try:
            await ws.send_text(json.dumps(
                {"type": "line", "stream": "out",
                 "text": line.decode("utf-8", errors="replace").rstrip("\r\n")}))
        except Exception:
            break
    code = await proc.wait()
    try:
        await ws.send_text(json.dumps({"type": "exit", "code": code}))
    except Exception:
        pass


def _is_running(proc):
    return proc is not None and proc.returncode is None


async def _send_error(ws, detail):
    await ws.send_text(json.dumps({"type": "error", "detail": detail}))


async def _read_message(ws):
    """One decoded client frame, or None when it was not valid JSON."""
    try:
        return json.loads(await ws.receive_text())
    except json.JSONDecodeError:
        await _send_error(ws, "JSON non valido")
        return None


async def _spawn(cmd):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
           "PYTHONUNBUFFERED": "1"}
    return await asyncio.create_subprocess_exec(
        *config.COMMAND_WHITELIST[cmd],
        cwd=str(config.PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env)


async def _start_command(ws, msg, proc):
    """Launch a whitelisted command; returns (proc, pump) or (proc, None) on refusal."""
    cmd = msg.get("cmd")
    if cmd not in config.COMMAND_WHITELIST:
        await _send_error(ws, f"comando '{cmd}' non in whitelist")
        return proc, None
    if _is_running(proc):
        await _send_error(ws, "un comando è già in esecuzione")
        return proc, None

    proc = await _spawn(cmd)
    await ws.send_text(json.dumps({"type": "start", "cmd": cmd}))
    return proc, asyncio.create_task(_stream(proc, ws))


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    if not await security.authorize_websocket(ws):
        return
    await ws.accept()
    proc = None
    pump = None
    try:
        while True:
            msg = await _read_message(ws)
            if msg is None:
                continue
            if msg.get("type") == "stop":
                if _is_running(proc):
                    proc.kill()
                continue
            proc, started = await _start_command(ws, msg, proc)
            if started is not None:
                pump = started
    except WebSocketDisconnect:
        pass
    finally:
        if _is_running(proc):
            proc.kill()
        if pump:
            pump.cancel()
