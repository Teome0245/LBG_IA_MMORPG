#!/usr/bin/env bash
# Installe le timer lbg-storage-watchdog-job sur la VM core (140).
# Crée des jobs Pilot (#/jobs) quand le pool thin Proxmox dépasse les seuils.
#
# Usage :
#   bash infra/scripts/install_storage_watchdog_job_vm.sh
#   LBG_CORE_VM_HOST=192.168.0.140 bash infra/scripts/install_storage_watchdog_job_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-storage-watchdog-job → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-storage-watchdog-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-storage-watchdog-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/storage_watchdog
sudo chown lbg:lbg /var/lib/lbg/storage_watchdog
sudo cp /tmp/lbg-storage-watchdog-job.service /tmp/lbg-storage-watchdog-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-storage-watchdog-job.timer
sudo systemctl start lbg-storage-watchdog-job.timer
systemctl is-active lbg-storage-watchdog-job.timer
systemctl list-timers lbg-storage-watchdog-job.timer --no-pager
EOF

echo ""
echo "Prérequis SSH Proxmox (une fois) — clé lbg@140 autorisée sur root@PVE :"
echo "  PUB=\$(ssh ${VM_USER}@${VM_HOST} 'cat ~/.ssh/id_ed25519.pub')"
echo "  ssh root@\${LBG_PROXMOX_SSH_HOST:-192.168.0.200} \"grep -qF \\\"\\\$PUB\\\" ~/.ssh/authorized_keys || echo \\\"\\\$PUB\\\" >> ~/.ssh/authorized_keys\""

echo ""
echo "OK — jobs visibles sur http://192.168.0.110:8080/#/jobs (filtrer actor: system:storage_watchdog)"
echo "Test manuel :"
echo "  ssh ${VM_USER}@${VM_HOST} 'sudo systemctl start lbg-storage-watchdog-job.service && journalctl -u lbg-storage-watchdog-job -n 20 --no-pager'"
