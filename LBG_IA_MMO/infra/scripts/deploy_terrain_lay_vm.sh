#!/usr/bin/env bash
# Déploie des fichiers terrain/*.lay en loose files dans le bin Core3 (lu avant les TRE).
#
# Usage :
#   bash infra/scripts/deploy_terrain_lay_vm.sh
#   bash infra/scripts/deploy_terrain_lay_vm.sh content/core3/terrain/poi_small.lay
#
# Prérequis : fichiers .lay extraits (extract_tre_asset.py) ou créés (Sytner IFF Editor).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CORE3_BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

if [[ $# -gt 0 ]]; then
  LAY_FILES=("$@")
else
  LAY_FILES=()
	for name in poi_small.lay poi_medium.lay poi_large.lay poi_bowl.lay; do
    p="${ROOT_DIR}/content/core3/terrain/${name}"
    if [[ -f "${p}" ]]; then
      LAY_FILES+=("${p}")
    fi
  done
fi

if [[ ${#LAY_FILES[@]} -eq 0 ]]; then
  echo "ERROR: aucun .lay à déployer." >&2
  echo "  Extraire depuis Aurora : python3 tools/client_patch/extract_tre_asset.py \\" >&2
  echo "    '/mnt/j/swgemu/StarWarsGalaxies - AURORA' terrain/road_torch_12x128_01.lay -o /tmp/test.lay" >&2
  echo "  Ou placer poi_small.lay dans content/core3/terrain/" >&2
  exit 1
fi

echo "=== Deploy terrain/*.lay → ${VM_USER}@${VM_HOST}:${CORE3_BIN}/terrain/ ==="
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${CORE3_BIN}/terrain"

for lay in "${LAY_FILES[@]}"; do
  base="$(basename "${lay}")"
  scp -q "${lay}" "${VM_USER}@${VM_HOST}:${CORE3_BIN}/terrain/${base}"
  echo "  + terrain/${base}"
done

echo "Redémarrer core3 pour recharger les templates terrain si besoin :"
echo "  bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
