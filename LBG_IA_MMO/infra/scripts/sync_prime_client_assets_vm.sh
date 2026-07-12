#!/usr/bin/env bash
# Sync assets Prime Client (maps + config minimap) vers VM core pour sondes M9.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${LBG_PRIME_CLIENT_ROOT:-${LBG_NEW_MMO_ROOT:+${LBG_NEW_MMO_ROOT}/prime-client}}"
SRC="${SRC:-/home/sdesh/projects/new_mmo/prime-client}"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
REMOTE="${LBG_PRIME_CLIENT_REMOTE:-/opt/new_mmo/prime-client}"

echo "=== Sync prime-client assets M9 → ${VM_USER}@${VM_HOST}:${REMOTE} ==="
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${REMOTE}/assets/maps ${REMOTE}/config ${REMOTE}/scripts ${REMOTE}/scenes/ui"
rsync -a "${SRC}/assets/maps/" "${VM_USER}@${VM_HOST}:${REMOTE}/assets/maps/"
rsync -a "${SRC}/config/minimap_config.json" "${VM_USER}@${VM_HOST}:${REMOTE}/config/"
rsync -a "${SRC}/scripts/minimap_hud.gd" "${VM_USER}@${VM_HOST}:${REMOTE}/scripts/"
rsync -a "${SRC}/scripts/planet_map_panel.gd" "${VM_USER}@${VM_HOST}:${REMOTE}/scripts/"
rsync -a "${SRC}/scripts/waypoint_store.gd" "${VM_USER}@${VM_HOST}:${REMOTE}/scripts/"
rsync -a "${SRC}/config/waypoints.json" "${VM_USER}@${VM_HOST}:${REMOTE}/config/"
rsync -a "${SRC}/scenes/ui/minimap_hud.tscn" "${VM_USER}@${VM_HOST}:${REMOTE}/scenes/ui/"
rsync -a "${SRC}/scenes/ui/planet_map_panel.tscn" "${VM_USER}@${VM_HOST}:${REMOTE}/scenes/ui/"
rsync -a "${SRC}/scenes/main.tscn" "${VM_USER}@${VM_HOST}:${REMOTE}/scenes/"
echo "OK — définir LBG_PRIME_CLIENT_ROOT=${REMOTE} dans /etc/lbg-ia-mmo.env sur 140"
