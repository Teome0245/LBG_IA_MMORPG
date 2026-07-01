#!/usr/bin/env bash
# Hygiène disque VM 245 (PreCu/patch) et 246 (Prime).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST_245="${LBG_PRECU_VM_HOST:-192.168.0.245}"
HOST_246="${LBG_PRIME_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_VM_USER:-lbg}"

run_on() {
  local host="$1"
  echo ""
  echo "========== ${host} =========="
  ssh "${VM_USER}@${host}" "bash -s" <<'REMOTE'
set -euo pipefail
echo "AVANT: $(df -h / | tail -1)"
rm -rf /opt/lbg-new-mmo/MMOCoreORB/build \
       /opt/lbg-new-mmo-clean/MMOCoreORB/build \
       /opt/lbg-antigravity/lbg-mmo/build 2>/dev/null || true
if [[ -d /opt/lbg-new-mmo-clean/MMOCoreORB/bin/log/zArchive ]]; then
  rm -rf /opt/lbg-new-mmo-clean/MMOCoreORB/bin/log/zArchive/*
fi
find /opt -path '*/MMOCoreORB/bin/log/*.log' -mtime +2 -delete 2>/dev/null || true
find /opt -path '*/bin/log/*.log' -size +80M 2>/dev/null | while read -r f; do
  tail -c 8388608 "$f" > "${f}.tail" && mv "${f}.tail" "$f"
done
rm -f /opt/lbg-new-mmo-clean/MMOCoreORB/bin/core3-clean.bad \
      /opt/lbg-new-mmo-clean/MMOCoreORB/bin/core3_new 2>/dev/null || true
sudo journalctl --vacuum-size=100M 2>/dev/null || true
sudo apt-get clean -y 2>/dev/null || true
sudo fstrim -av 2>/dev/null || true
echo "APRÈS: $(df -h / | tail -1)"
REMOTE
}

run_on "${HOST_246}"
run_on "${HOST_245}"

echo ""
echo "Terminé. Sur Proxmox (lbgr720), vérifier: lvs vg_data"
