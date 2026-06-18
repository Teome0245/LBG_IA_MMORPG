#!/usr/bin/env bash
# Agent export World Editor : merge JSON + commit Git (branche world-editor/auto).
set -euo pipefail

ROOT="${LBG_IA_MMO_ROOT:-/opt/LBG_IA_MMO}"
BIN="${CORE3_BIN:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
QUEUE="${BIN}/ia_bridge/world_editor_export.queue"
PROCESSED="${BIN}/ia_bridge/world_editor_export.processed"
MERGE="${ROOT}/tools/world_editor/merge_export.py"
GIT_BRANCH="${LBG_WORLD_EXPORT_BRANCH:-world-editor/auto}"
GIT_REMOTE="${LBG_WORLD_EXPORT_REMOTE:-origin}"

if [[ ! -f "${QUEUE}" ]]; then
  exit 0
fi

if [[ ! -s "${QUEUE}" ]]; then
  exit 0
fi

echo "=== World Editor export agent $(date -Iseconds) ==="

python3 "${MERGE}" "${ROOT}" "${BIN}"

cd "${ROOT}"
if [[ -d .git ]]; then
  git config user.email "${LBG_WORLD_EXPORT_GIT_EMAIL:-lbg-world-export@local}"
  git config user.name "${LBG_WORLD_EXPORT_GIT_NAME:-LBG World Export Agent}"
  git fetch "${GIT_REMOTE}" 2>/dev/null || true
  git checkout -B "${GIT_BRANCH}" 2>/dev/null || git checkout "${GIT_BRANCH}"
  git add content/core3/world_poi/ content/core3/core3_npc_catalog.json \
    content/core3/locations/mos_eisley_training_center.json \
    content/core3/locations/lost_heaven_hub.json 2>/dev/null || true
  if git diff --cached --quiet; then
    echo "Aucun changement Git."
  else
    MSG="world-editor: export $(date -Iseconds)"
    git commit -m "${MSG}"
    if [[ "${LBG_WORLD_EXPORT_PUSH:-1}" == "1" ]]; then
      git push -u "${GIT_REMOTE}" "${GIT_BRANCH}" || echo "WARN: push failed (review local commit)"
    fi
  fi
else
  echo "WARN: ${ROOT} n est pas un depot Git — merge fichiers seulement."
fi

# Ack queue
if [[ -f "${QUEUE}" ]]; then
  cat "${QUEUE}" >> "${PROCESSED}" 2>/dev/null || true
  : > "${QUEUE}"
fi

echo "=== Export agent done ==="
