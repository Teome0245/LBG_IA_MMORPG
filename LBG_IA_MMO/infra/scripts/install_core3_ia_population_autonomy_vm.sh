#!/usr/bin/env bash
# Active lbg-core3-ia-population-autonomy sur Prime (246).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Install population-autonomy → ${VM_USER}@${VM_HOST} ==="

rsync -az \
  "${ROOT_DIR}/agents/src/lbg_agents/" \
  "${VM_USER}@${VM_HOST}:/opt/LBG_IA_MMO/agents/src/lbg_agents/"

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-population-autonomy.service" \
  "${ROOT_DIR}/tools/core3_ia_lia_autonomy_loop.py" \
  "${ROOT_DIR}/content/core3/core3_ia_players.json" \
  "${ROOT_DIR}/content/core3/core3_behavior_profiles.json" \
  "${ROOT_DIR}/content/core3/core3_npc_catalog.json" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo apt-get install -y -qq python3-httpx 2>/dev/null || true
sudo cp /tmp/lbg-core3-ia-population-autonomy.service /etc/systemd/system/
sudo cp /tmp/core3_ia_lia_autonomy_loop.py /opt/LBG_IA_MMO/tools/core3_ia_lia_autonomy_loop.py
sudo cp /tmp/core3_ia_players.json /opt/LBG_IA_MMO/content/core3/core3_ia_players.json
sudo cp /tmp/core3_behavior_profiles.json /opt/LBG_IA_MMO/content/core3/core3_behavior_profiles.json
sudo cp /tmp/core3_npc_catalog.json /opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json
sudo systemctl daemon-reload
sudo systemctl enable --now lbg-core3-ia-population-autonomy.service
sleep 2
systemctl is-active lbg-core3-ia-population-autonomy.service
journalctl -u lbg-core3-ia-population-autonomy -n 5 --no-pager
EOF

echo "OK"
