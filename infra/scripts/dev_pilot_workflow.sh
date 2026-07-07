#!/usr/bin/env bash
# Raccourci depuis la racine LBG_IA_MMORPG → LBG_IA_MMO/infra/scripts/dev_pilot_workflow.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${ROOT}/LBG_IA_MMO/infra/scripts/dev_pilot_workflow.sh"
if [[ ! -f "${TARGET}" ]]; then
  echo "Script introuvable : ${TARGET}" >&2
  echo "Essayez : cd LBG_IA_MMO && bash infra/scripts/dev_pilot_workflow.sh $*" >&2
  exit 1
fi
exec bash "${TARGET}" "$@"
