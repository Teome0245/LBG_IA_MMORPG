#!/usr/bin/env bash
# Applique le terrain Lost Heaven côté serveur SANS connexion client.
# Équivalent headless de :
#   lbg_we terrain clear all
#   lbg_we terrain base 50 9 450 0
#   lbg_we terrain status
#
# hub goto reste IG (téléport joueur).
#
# Usage :
#   bash infra/scripts/apply_lbg_terrain_base_vm.sh
#   bash infra/scripts/apply_lbg_terrain_base_vm.sh --wait 45
#   bash infra/scripts/apply_lbg_terrain_base_vm.sh --action status

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
IA="${BIN}/ia_bridge"

#   lbg_we terrain base 50 9 450 0
# Flatten serveur : poi_large.lay (64 m) — recouvre pas 50 m (poi_small 16 m laissait des dunes visibles).
LAY="terrain/poi_large.lay"
STEP=50
HALF=9
BOWL_R=450
BOWL_Z=0
CX=4749
CY=-737
ACTION="pipeline"
WAIT_SEC=90

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wait) WAIT_SEC="${2:-30}"; shift 2 ;;
    --action) ACTION="$2"; shift 2 ;;
    --step) STEP="$2"; shift 2 ;;
    --half) HALF="$2"; shift 2 ;;
    --bowl-radius) BOWL_R="$2"; shift 2 ;;
    --bowl-z) BOWL_Z="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--wait SEC] [--action pipeline|clear|base|status|replay]"
      exit 0
      ;;
    *) echo "Option inconnue: $1" >&2; exit 1 ;;
  esac
done

echo "=== Terrain headless → ${VM_USER}@${VM_HOST} (action=${ACTION}) ==="

ssh "${VM_USER}@${VM_HOST}" bash -s <<EOF
set -euo pipefail
IA="${IA}"
mkdir -p "\${IA}"
rm -f "\${IA}/lbg_we_terrain_apply.flag" "\${IA}/lbg_we_terrain_apply.result.json"
cat > "\${IA}/lbg_we_terrain_apply.json" <<JSON
{"action":"${ACTION}","cx":${CX},"cy":${CY},"step":${STEP},"halfCells":${HALF},"bowlRadius":${BOWL_R},"bowlZ":${BOWL_Z},"lay":"${LAY}","clearFirst":true}
JSON
touch "\${IA}/lbg_we_terrain_apply.flag"
echo "  requête posée (\${IA}/lbg_we_terrain_apply.flag)"
EOF

echo "Attente résultat (max ${WAIT_SEC}s)..."
deadline=$((SECONDS + WAIT_SEC))
while (( SECONDS < deadline )); do
  if ssh "${VM_USER}@${VM_HOST}" "test -f ${IA}/lbg_we_terrain_apply.result.json"; then
    echo ""
    ssh "${VM_USER}@${VM_HOST}" "cat ${IA}/lbg_we_terrain_apply.result.json"
    echo ""
    ssh "${VM_USER}@${VM_HOST}" "grep -E 'headless base|headless terrain' /tmp/core3-clean.log /opt/lbg-new-mmo-clean/MMOCoreORB/bin/log/core3.log 2>/dev/null | tail -3 || true"
    exit 0
  fi
  sleep 2
done

echo "TIMEOUT — Core3 actif ? Lua déployé ? Vérifier :" >&2
echo "  ssh ${VM_USER}@${VM_HOST} 'systemctl is-active lbg-core3-prime; ls -la ${IA}/lbg_we_terrain_apply.*'" >&2
exit 1
