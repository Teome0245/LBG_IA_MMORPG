#!/usr/bin/env bash
# Lance lbg_gateway sur la VM MMO (port 50000) en lecture snapshots Core3.
set -euo pipefail

HOST="${LBG_GATEWAY_SSH_HOST:-192.168.0.245}"
USER="${LBG_GATEWAY_SSH_USER:-lbg}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_DIR="${LBG_GATEWAY_REMOTE_DIR:-/home/lbg/lbg-gateway}"

echo "[gateway] sync + start on ${USER}@${HOST} (${REMOTE_DIR})"
ssh "${USER}@${HOST}" "mkdir -p ${REMOTE_DIR}"
scp -q "${ROOT}/services/lbg_gateway/main.py" "${USER}@${HOST}:${REMOTE_DIR}/main.py"
scp -q "${ROOT}/services/lbg_gateway/dialogue_ia.py" "${USER}@${HOST}:${REMOTE_DIR}/dialogue_ia.py"
scp -q "${ROOT}/services/lbg_gateway/catalog_context.py" "${USER}@${HOST}:${REMOTE_DIR}/catalog_context.py"
scp -q "${ROOT}/services/lbg_gateway/world_coords.py" "${USER}@${HOST}:${REMOTE_DIR}/world_coords.py"
scp -q "${ROOT}/services/lbg_gateway/zone_players.py" "${USER}@${HOST}:${REMOTE_DIR}/zone_players.py"
scp -q "${ROOT}/services/lbg_gateway/pending_bridge.py" "${USER}@${HOST}:${REMOTE_DIR}/pending_bridge.py"
scp -q "${ROOT}/services/lbg_gateway/roster_filter.py" "${USER}@${HOST}:${REMOTE_DIR}/roster_filter.py"
scp -q "${ROOT}/services/lbg_gateway/lbg_ws2.py" "${USER}@${HOST}:${REMOTE_DIR}/lbg_ws2.py"
scp -q "${ROOT}/services/lbg_gateway/zone_bridge_feed.py" "${USER}@${HOST}:${REMOTE_DIR}/zone_bridge_feed.py"
scp -q "${ROOT}/content/core3/core3_npc_catalog.json" "${USER}@${HOST}:${REMOTE_DIR}/core3_npc_catalog.json"
ssh "${USER}@${HOST}" "mkdir -p ${REMOTE_DIR}/locations"
scp -q "${ROOT}"/content/core3/locations/*.json "${USER}@${HOST}:${REMOTE_DIR}/locations/"

ssh "${USER}@${HOST}" "REMOTE_DIR='${REMOTE_DIR}' bash -s" <<'EOF'
set -euo pipefail
export LBG_GATEWAY_HOST=0.0.0.0
export LBG_GATEWAY_PORT=50000
export LBG_GATEWAY_SNAPSHOTS=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/npc_snapshots.json
export LBG_GATEWAY_PLAYER_SNAPSHOTS=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/player_snapshots.json
export LBG_GATEWAY_TRACK_PLAYERS="${LBG_GATEWAY_TRACK_PLAYERS:-Teome,Lia,Nix}"
export LBG_GATEWAY_CATALOG="${REMOTE_DIR}/core3_npc_catalog.json"
export LBG_GATEWAY_LOCATIONS="${REMOTE_DIR}/locations"
export LBG_GATEWAY_ZONE_BRIDGE_LIVE=1
export LBG_GATEWAY_ZONE_BRIDGE_JSON=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/zone_bridge_live.json
export LBG_GATEWAY_TICK_LIVE_S=0.05
# Pont IA : mêmes variables que mmmorpg si présentes sur la VM
if [ -f /etc/lbg-ia-mmo.env ]; then
  set -a
  # shellcheck disable=SC1091
  . /etc/lbg-ia-mmo.env
  set +a
fi
export LBG_GATEWAY_IA_BACKEND_URL="${LBG_GATEWAY_IA_BACKEND_URL:-${MMMORPG_IA_BACKEND_URL:-}}"
export LBG_GATEWAY_IA_BACKEND_TOKEN="${LBG_GATEWAY_IA_BACKEND_TOKEN:-${MMMORPG_IA_BACKEND_TOKEN:-}}"
python3 -m pip install --user -q websockets httpx 2>/dev/null || pip3 install --user -q websockets httpx
pkill -f "${REMOTE_DIR}/main.py" 2>/dev/null || true
nohup python3 "${REMOTE_DIR}/main.py" >> /tmp/lbg-gateway.log 2>&1 &
sleep 1
if ss -tlnp 2>/dev/null | grep -q ':50000 '; then
  echo "[gateway] OK ws://0.0.0.0:50000"
else
  echo "[gateway] WARN port 50000 not listening"
  tail -25 /tmp/lbg-gateway.log 2>/dev/null || true
fi
EOF
