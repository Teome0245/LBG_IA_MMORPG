#!/usr/bin/env bash
# Installe lbg-gateway comme service systemd sur la VM (port 50000).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
REMOTE_DIR="/home/lbg/lbg-gateway"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

echo "=== Install lbg-gateway systemd (${VM_USER}@${VM_HOST}) ==="
bash "${ROOT_DIR}/infra/scripts/run_lbg_gateway_vm.sh"

scp -q "${ROOT_DIR}/infra/systemd/lbg-gateway.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-gateway.service"

ssh "${VM_USER}@${VM_HOST}" "REMOTE_DIR='${REMOTE_DIR}' BIN='${BIN}' bash -s" <<'EOF'
set -euo pipefail
sudo tee "${REMOTE_DIR}/gateway.env" >/dev/null <<ENV
LBG_GATEWAY_HOST=0.0.0.0
LBG_GATEWAY_PORT=50000
LBG_GATEWAY_SNAPSHOTS=${BIN}/ia_bridge/npc_snapshots.json
LBG_GATEWAY_PLAYER_SNAPSHOTS=${BIN}/ia_bridge/player_snapshots.json
LBG_GATEWAY_TRACK_PLAYERS=Teome,Lia,Nix
LBG_GATEWAY_CATALOG=${REMOTE_DIR}/core3_npc_catalog.json
LBG_GATEWAY_LOCATIONS=${REMOTE_DIR}/locations
LBG_GATEWAY_PENDING_FILE=${BIN}/ia_bridge/pending.jsonl
LBG_GATEWAY_INJECT_MOVE=0
LBG_GATEWAY_INJECT_PLAYER=Teome
ENV
sudo cp /tmp/lbg-gateway.service /etc/systemd/system/lbg-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable lbg-gateway.service
sudo systemctl restart lbg-gateway.service
systemctl is-active lbg-gateway.service
ss -tlnp 2>/dev/null | grep ':50000 ' || true
EOF

echo "OK — ws://${VM_HOST}:50000 (systemd lbg-gateway.service)"
