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


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    if not await security.authorize_websocket(ws):
        return
    await ws.accept()
    proc = None
    pump = None
    try:
        while True:
            try:
                msg = json.loads(await ws.receive_text())
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "detail": "JSON non valido"}))
                continue

            if msg.get("type") == "stop":
                if proc and proc.returncode is None:
                    proc.kill()
                continue

            cmd = msg.get("cmd")
            if cmd not in config.COMMAND_WHITELIST:
                await ws.send_text(json.dumps(
                    {"type": "error", "detail": f"comando '{cmd}' non in whitelist"}))
                continue
            if proc and proc.returncode is None:
                await ws.send_text(json.dumps(
                    {"type": "error", "detail": "un comando è già in esecuzione"}))
                continue

            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
                   "PYTHONUNBUFFERED": "1"}
            proc = await asyncio.create_subprocess_exec(
                *config.COMMAND_WHITELIST[cmd],
                cwd=str(config.PROJECT_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env)
            await ws.send_text(json.dumps({"type": "start", "cmd": cmd}))
            pump = asyncio.create_task(_stream(proc, ws))
    except WebSocketDisconnect:
        pass
    finally:
        if proc and proc.returncode is None:
            proc.kill()
        if pump:
            pump.cancel()
