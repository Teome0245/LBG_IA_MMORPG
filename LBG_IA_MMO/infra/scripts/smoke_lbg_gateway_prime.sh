#!/usr/bin/env bash
# Smoke lbg_gateway port 50000 (lbg-ws/1).
set -euo pipefail

HOST="${1:-192.168.0.245}"
if [[ "${1:-}" == "--host" ]]; then
  HOST="${2:-127.0.0.1}"
fi
PORT="${LBG_GATEWAY_PORT:-50000}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$ROOT/.venv-smoke-ws"
PY="python3"
if ! python3 -c "import websockets" 2>/dev/null; then
  [[ -x "$VENV/bin/python" ]] || { python3 -m venv "$VENV" && "$VENV/bin/pip" install -q websockets; }
  PY="$VENV/bin/python"
fi

export SMOKE_WS_URL="ws://${HOST}:${PORT}"
"$PY" <<'PY'
import asyncio, json, os, sys
import websockets

URL = os.environ["SMOKE_WS_URL"]

async def main():
    print(f"[smoke] gateway {URL}")
    async with websockets.connect(URL, open_timeout=8) as ws:
        await ws.send(json.dumps({"type": "login", "username": "smoke", "password": "x"}))
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        assert m.get("type") == "login_result" and m.get("success"), m
        await ws.send(json.dumps({"type": "get_characters"}))
        m = json.loads(await ws.recv())
        assert m.get("type") == "characters_list", m
        await ws.send(json.dumps({"type": "select_character", "character_id": 1}))
        m = json.loads(await ws.recv())
        assert m.get("type") == "enter_world", m
        n = len(m.get("entities") or [])
        print(f"[smoke] enter_world entities={n} map={m.get('map')}")
        if n < 1:
            print("[smoke] WARN: aucun PNJ (snapshots vides ?)")
    print("[smoke] gateway OK")

asyncio.run(main())
PY
