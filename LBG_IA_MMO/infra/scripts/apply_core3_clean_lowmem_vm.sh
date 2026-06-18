#!/usr/bin/env bash
# Applique le profil mémoire réduit pour core3-clean + swap optionnel sur la VM 245.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CONF="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Profil low-mem core3-clean sur ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
CONF="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua"

# Ajouter / mettre à jour le bloc low-mem (Lua charge config-local après config.lua)
cat >> "${CONF}" <<'LUA'

-- low-mem dual-instance (ajouté par apply_core3_clean_lowmem_vm.sh)
Core3.ZoneProcessingThreads = 4
Core3.ZoneAllowedConnections = 500
-- Zones : ne pas surcharger ici (liste complète dans config.lua)
LUA

# Swap 4 Go si absent
if ! swapon --show | grep -q /swapfile-core3; then
  if [[ ! -f /swapfile-core3 ]]; then
    sudo fallocate -l 4G /swapfile-core3 || sudo dd if=/dev/zero of=/swapfile-core3 bs=1M count=4096
    sudo chmod 600 /swapfile-core3
    sudo mkswap /swapfile-core3
  fi
  sudo swapon /swapfile-core3
  echo "Swap activé : $(swapon --show | grep core3)"
fi

free -h
REMOTE

echo "Relancer clean : bash infra/scripts/start_core3_dual_vm.sh"
echo "  (ou : ssh … 'cd /opt/lbg-new-mmo-clean/MMOCoreORB/bin && nohup ./core3-clean >> /tmp/core3-clean.log 2>&1 &')"
