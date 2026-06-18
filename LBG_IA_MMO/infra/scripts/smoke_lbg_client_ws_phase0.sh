#!/usr/bin/env bash
# Smoke Phase 0 — client LBG / mmmorpg WebSocket (sans Godot).
set -euo pipefail

HOST="${1:-192.168.0.245}"
if [[ "${1:-}" == "--host" ]]; then
  HOST="${2:-127.0.0.1}"
fi
PORT="${MMMORPG_PORT:-7733}"
URL="ws://${HOST}:${PORT}"
PLAYER="smoke_godot_phase0_$$"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv-smoke-ws"
PY="python3"
if ! python3 -c "import websockets" 2>/dev/null; then
  if [[ ! -x "$VENV/bin/python" ]]; then
    echo "[smoke] création venv $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q websockets
  fi
  PY="$VENV/bin/python"
fi

export SMOKE_WS_URL="$URL"
export SMOKE_PLAYER="$PLAYER"

"$PY" <<'PY'
import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("websockets manquant")
    sys.exit(0)

URL = os.environ["SMOKE_WS_URL"]
PLAYER = os.environ["SMOKE_PLAYER"]

async def main() -> None:
    print(f"[smoke] connect {URL}")
    async with websockets.connect(URL, open_timeout=8) as ws:
        await ws.send(json.dumps({"type": "hello", "player_name": PLAYER}))
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msg = json.loads(raw)
        assert msg.get("type") == "welcome", msg
        ents = msg.get("entities") or []
        print(f"[smoke] welcome ok player_id={msg.get('player_id')} entities={len(ents)}")
        await ws.send(json.dumps({"type": "move", "x": 1.0, "y": 0.0, "z": 2.0}))
        for _ in range(30):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                m = json.loads(raw)
                if m.get("type") == "world_tick":
                    print(f"[smoke] world_tick entities={len(m.get('entities') or [])}")
                    break
            except asyncio.TimeoutError:
                continue
        else:
            print("[smoke] WARN: pas de world_tick en 60s (serveur lent ou tick off)")
    print("[smoke] OK")

asyncio.run(main())
PY

echo "[smoke] lbg_client_godot phase0 — terminé"
