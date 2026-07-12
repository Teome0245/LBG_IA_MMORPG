#!/usr/bin/env bash
# Sync POI serveur Scrapaltai → assets Godot Prime Client (M9a-3).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_ROOT="${LBG_PRIME_CLIENT_ROOT:-${LBG_NEW_MMO_ROOT:+${LBG_NEW_MMO_ROOT}/prime-client}}"
PRIME_ROOT="${PRIME_ROOT:-/home/sdesh/projects/new_mmo/prime-client}"
EDITOR_ROOT="${LBG_WORLD_EDITOR_ROOT:-${ROOT_DIR}/tools/world_editor}"
POI_ONLY="${LBG_SCRAPALTAI_SYNC_POI_ONLY:-1}"

ARGS=(--repo-root "${ROOT_DIR}" --editor-root "${EDITOR_ROOT}" --out "${PRIME_ROOT}")
if [[ "${POI_ONLY}" == "1" ]]; then
  ARGS+=(--poi-only)
fi

echo "=== Sync Scrapaltai POI → ${PRIME_ROOT}/assets/maps ==="
python3 "${ROOT_DIR}/tools/map_export/export_scrapaltai_for_godot.py" "${ARGS[@]}"
echo "OK"
