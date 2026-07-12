#!/usr/bin/env bash
# Installe le timer watchdog SOE login Prime (sonde Bot_IA/Lia).
#
# Usage :
#   bash infra/scripts/install_core3_prime_soe_login_watchdog_vm.sh
#   LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/install_core3_prime_soe_login_watchdog_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Install watchdog SOE login Prime → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/scripts/watch_core3_prime_soe_login_health.sh" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-soe-login-watchdog.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-soe-login-watchdog.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p /var/lib/lbg/core3_prime_soe_watchdog
sudo chown lbg:lbg /var/lib/lbg/core3_prime_soe_watchdog
sudo cp /tmp/watch_core3_prime_soe_login_health.sh /opt/LBG_IA_MMO/infra/scripts/
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_soe_login_health.sh
sudo cp /tmp/lbg-core3-prime-soe-login-watchdog.service /tmp/lbg-core3-prime-soe-login-watchdog.timer /etc/systemd/system/
if ! grep -q LBG_CLIENT_PRIME_LBG_DIR /etc/lbg-ia-mmo.env 2>/dev/null; then
  echo 'LBG_CLIENT_PRIME_LBG_DIR=/home/lbg/client-prime-lbg' | sudo tee -a /etc/lbg-ia-mmo.env >/dev/null
fi
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-prime-soe-login-watchdog.timer
sudo systemctl restart lbg-core3-prime-soe-login-watchdog.timer
systemctl list-timers lbg-core3-prime-soe-login-watchdog.timer --no-pager || true
EOF

echo "OK — timer SOE login actif (3 min). Dry-run :"
ssh "${VM_USER}@${VM_HOST}" \
  "bash /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_soe_login_health.sh --dry-run --json" || true
