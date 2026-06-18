#!/usr/bin/env bash
# Installe le timer lbg-infra-watchdog sur la VM core (140).
#
# Usage :
#   bash infra/scripts/install_infra_watchdog_vm.sh
#   LBG_CORE_VM_HOST=192.168.0.140 bash infra/scripts/install_infra_watchdog_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-infra-watchdog → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-infra-watchdog.service" \
  "${ROOT_DIR}/infra/systemd/lbg-infra-watchdog.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo cp /tmp/lbg-infra-watchdog.service /tmp/lbg-infra-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-infra-watchdog.timer
sudo systemctl start lbg-infra-watchdog.timer
systemctl is-active lbg-infra-watchdog.timer
systemctl list-timers lbg-infra-watchdog.timer --no-pager
EOF

echo ""
echo "OK — timer actif (5 min). Test manuel :"
echo "  ssh ${VM_USER}@${VM_HOST} 'sudo systemctl start lbg-infra-watchdog.service && journalctl -u lbg-infra-watchdog -n 30 --no-pager'"
