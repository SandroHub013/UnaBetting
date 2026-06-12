#!/usr/bin/env bash
# scripts/ci/run_dashboard_smoke.sh — Start dashboard server and run smoke tests.

set -euo pipefail

echo "[CI] Starting FastAPI server..."
python -m src.dashboard --server-only > /tmp/dashboard.log 2>&1 &
SERVER_PID=$!
sleep 3

cleanup() {
    kill $SERVER_PID 2>/dev/null || true
}
trap cleanup EXIT

echo "[CI] Health check /api/overview..."
curl -f http://127.0.0.1:8765/api/overview

echo "[CI] Health check /api/bets..."
curl -f http://127.0.0.1:8765/api/bets

echo "[CI] WS whitelist rejection..."
python -c "
import asyncio, json, websockets
async def t():
    async with websockets.connect('ws://127.0.0.1:8765/ws/run') as ws:
        await ws.send(json.dumps({'cmd': 'rm -rf /'}))
        msg = json.loads(await ws.recv())
        assert msg['type'] == 'error' and 'whitelist' in msg['detail']
asyncio.run(t())
"

echo "[CI] Path traversal protection..."
curl -f -o /dev/null -s -w '%{http_code}' 'http://127.0.0.1:8765/api/file?path=../secrets' | grep -q 403

echo "[CI] Dashboard smoke tests passed."
