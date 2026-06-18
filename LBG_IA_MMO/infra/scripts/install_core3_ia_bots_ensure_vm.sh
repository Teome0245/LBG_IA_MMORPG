#!/usr/bin/env bash
# Installe le timer lbg-core3-ia-bots-ensure sur Prime (246).
#
# Usage :
#   bash infra/scripts/install_core3_ia_bots_ensure_vm.sh
#   LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/install_core3_ia_bots_ensure_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Install lbg-core3-ia-bots-ensure → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-bots-ensure.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-bots-ensure.timer" \
  "${ROOT_DIR}/infra/scripts/run_ensure_ia_bots.sh" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo apt-get install -y -qq python3-httpx 2>/dev/null || true
sudo mkdir -p /opt/LBG_IA_MMO/infra/scripts
sudo cp /tmp/lbg-core3-ia-bots-ensure.service /tmp/lbg-core3-ia-bots-ensure.timer /etc/systemd/system/
sudo cp /tmp/run_ensure_ia_bots.sh /opt/LBG_IA_MMO/infra/scripts/run_ensure_ia_bots.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/run_ensure_ia_bots.sh
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-ia-bots-ensure.timer
sudo systemctl start lbg-core3-ia-bots-ensure.timer
systemctl is-active lbg-core3-ia-bots-ensure.timer
sudo systemctl start lbg-core3-ia-bots-ensure.service
EOF

echo "OK — timer bots 5 min + run immediat"
