#!/usr/bin/env bash
# Smoke M9c — carte planétaire M + waypoints Prime Client.
set -euo pipefail

PRIME_ROOT="${LBG_PRIME_CLIENT_ROOT:-${LBG_NEW_MMO_ROOT:+${LBG_NEW_MMO_ROOT}/prime-client}}"
PRIME_ROOT="${PRIME_ROOT:-/home/sdesh/projects/new_mmo/prime-client}"

fail=0
check() {
  if [[ -f "$1" ]]; then echo "OK $1"; else echo "KO $1"; fail=1; fi
}

check "${PRIME_ROOT}/scripts/planet_map_panel.gd"
check "${PRIME_ROOT}/scenes/ui/planet_map_panel.tscn"
check "${PRIME_ROOT}/scripts/waypoint_store.gd"
check "${PRIME_ROOT}/config/waypoints.json"
check "${PRIME_ROOT}/assets/maps/locations_tree.json"

if grep -q "planet_map_panel" "${PRIME_ROOT}/scenes/main.tscn" 2>/dev/null; then
  echo "OK main.tscn contient planet_map_panel"
else
  echo "KO main.tscn sans planet_map_panel"
  fail=1
fi

[[ "${fail}" -eq 0 ]] || exit 2
echo "Smoke M9c carte M OK"
