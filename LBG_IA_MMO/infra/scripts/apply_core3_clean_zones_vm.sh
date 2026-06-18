#!/usr/bin/env bash
# Configure Core3.ZonesEnabled sur Serveur Prime (core3-clean).
# Défaut : aucune surcharge → toutes les zones de config.lua (+ espace).
#
# Usage :
#   bash infra/scripts/apply_core3_clean_zones_vm.sh              # tout débloquer
#   CORE3_ZONES_ENABLED='tatooine,tutorial' bash ...              # liste explicite

set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CONF="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua"
ZONES_RAW="${CORE3_ZONES_ENABLED:-}"

if [[ -z "${ZONES_RAW}" ]]; then
  echo "=== Zones Prime → défaut config.lua (toutes planètes + espace) ==="
else
  IFS=',' read -ra ZONES <<< "${ZONES_RAW}"
  LUA_LIST=""
  for z in "${ZONES[@]}"; do
    z="$(echo "$z" | xargs)"
    [[ -n "$z" ]] || continue
    LUA_LIST+="\"${z}\", "
  done
  LUA_LIST="${LUA_LIST%, }"
  echo "=== Zones Prime → { ${LUA_LIST} } ==="
fi

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<REMOTE
set -euo pipefail
CONF="${CONF}"
touch "\${CONF}"
ZONES_RAW='${ZONES_RAW}'
if [[ -z "\${ZONES_RAW}" ]]; then
  sed -i '/^Core3.ZonesEnabled/d' "\${CONF}"
  sed -i '/^Core3.SpaceZonesEnabled/d' "\${CONF}"
  echo "(pas de surcharge — défaut config.lua)"
else
  LUA_LIST='${LUA_LIST:-}'
  sed -i '/^Core3.ZonesEnabled/d' "\${CONF}"
  sed -i '/^Core3.SpaceZonesEnabled/d' "\${CONF}"
  echo "Core3.ZonesEnabled = { \${LUA_LIST} }" >> "\${CONF}"
  echo 'Core3.SpaceZonesEnabled = {}' >> "\${CONF}"
fi
grep -E 'ZonesEnabled|SpaceZones' "\${CONF}" 2>/dev/null || true
grep -c tatooine /opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config.lua
REMOTE

echo "Relancer : pkill -x core3-clean; cd /opt/lbg-new-mmo-clean/MMOCoreORB/bin && nohup ./core3-clean > /tmp/core3-clean.log 2>&1 &"
