#!/usr/bin/env bash
# Serveur Prime (core3-clean) : n'active que Tatooine (pont IA / monde vivant ciblé).
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CONF="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua"
ZONE="${CORE3_IA_ZONE:-tatooine}"

echo "=== Zones Prime → ${ZONE} uniquement (${VM_USER}@${VM_HOST}) ==="

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<REMOTE
set -euo pipefail
CONF="${CONF}"
ZONE="${ZONE}"
touch "\${CONF}"

if grep -q 'Core3.ZonesEnabled' "\${CONF}"; then
  sed -i 's/Core3.ZonesEnabled = {[^}]*}/Core3.ZonesEnabled = { "'"\${ZONE}"'" }/' "\${CONF}"
else
  cat >> "\${CONF}" <<LUA

-- ia-tatooine-only (apply_core3_clean_tatooine_only_vm.sh)
Core3.ZonesEnabled = { "\${ZONE}" }
Core3.SpaceZonesEnabled = {}
LUA
fi

grep -E 'ZonesEnabled|SpaceZones' "\${CONF}" | tail -5
REMOTE

echo "Relancer clean : bash infra/scripts/start_core3_dual_vm.sh  (ou restart core3-clean seul)"
