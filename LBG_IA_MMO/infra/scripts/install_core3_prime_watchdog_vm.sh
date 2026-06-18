#!/usr/bin/env bash
# Installe le timer watchdog login Prime sur la VM MMO (245).
#
# Usage :
#   bash infra/scripts/install_core3_prime_watchdog_vm.sh
#   bash infra/scripts/install_core3_prime_watchdog_vm.sh --dry-run-check

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
DRY_CHECK=0
for arg in "$@"; do
  case "$arg" in
    --dry-run-check) DRY_CHECK=1 ;;
  esac
done

echo "=== Install watchdog Prime login → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/scripts/watch_core3_prime_login_health.sh" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-watchdog.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-watchdog.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/core3_prime_watchdog
sudo chown lbg:lbg /var/lib/lbg/core3_prime_watchdog
sudo cp /tmp/watch_core3_prime_login_health.sh /opt/LBG_IA_MMO/infra/scripts/
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_login_health.sh
sudo cp /tmp/lbg-core3-prime-watchdog.service /tmp/lbg-core3-prime-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-prime-watchdog.timer
sudo systemctl restart lbg-core3-prime-watchdog.timer
systemctl list-timers lbg-core3-prime-watchdog.timer --no-pager || true
EOF

if [[ "${DRY_CHECK}" == "1" ]]; then
  echo "=== Dry-run check ==="
  ssh "${VM_USER}@${VM_HOST}" \
    "bash /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_login_health.sh --dry-run --json" || true
fi

echo "OK — timer actif (5 min). Logs : journalctl -u lbg-core3-prime-watchdog.service"
