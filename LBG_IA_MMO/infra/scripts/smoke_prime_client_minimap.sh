#!/usr/bin/env bash
# Smoke M9b — minimap HUD Prime Client (fichiers + grep scène).
set -euo pipefail

PRIME_ROOT="${LBG_PRIME_CLIENT_ROOT:-${LBG_NEW_MMO_ROOT:+${LBG_NEW_MMO_ROOT}/prime-client}}"
PRIME_ROOT="${PRIME_ROOT:-/home/sdesh/projects/new_mmo/prime-client}"

fail=0
check() {
  if [[ -f "$1" ]]; then
    echo "OK $1"
  else
    echo "KO $1"
    fail=1
  fi
}

check "${PRIME_ROOT}/scripts/minimap_hud.gd"
check "${PRIME_ROOT}/scenes/ui/minimap_hud.tscn"
check "${PRIME_ROOT}/config/minimap_config.json"

if grep -q "minimap_hud" "${PRIME_ROOT}/scenes/main.tscn" 2>/dev/null; then
  echo "OK main.tscn contient minimap_hud"
else
  echo "KO main.tscn sans minimap_hud"
  fail=1
fi

if [[ "${fail}" -ne 0 ]]; then
  exit 2
fi
echo "Smoke M9b minimap OK"
