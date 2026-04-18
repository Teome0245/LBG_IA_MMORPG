#!/usr/bin/env bash
set -euo pipefail

# Smoke "CI style" (LAN) : petite suite stable et non-interactive.
#
# Usage:
#   bash infra/scripts/smoke_lan_ci.sh
#
# Vars:
#   CORE_HOST (defaut 192.168.0.140)
#   MMO_HOST  (defaut 192.168.0.245)
#   RUN_LLM   (defaut 1) : si 0 => ne lance pas les smokes dépendants du LLM

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

CORE_HOST="${CORE_HOST:-192.168.0.140}"
MMO_HOST="${MMO_HOST:-192.168.0.245}"
RUN_LLM="${RUN_LLM:-1}"

echo "=== smoke_lan_ci ==="
echo "core=${CORE_HOST} mmo=${MMO_HOST} run_llm=${RUN_LLM}"

export LBG_CORE_HOST="${CORE_HOST}"
export LBG_MMO_HOST="${MMO_HOST}"

echo
echo "== 1) minimal (healthz + snapshot + route) =="
bash infra/scripts/smoke_lan_minimal.sh

if [ "${RUN_LLM}" = "1" ]; then
  echo
  echo "== 2) dialogue LLM -> ACTION_JSON -> commit (aid) =="
  LBG_SMOKE_TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-240}" bash infra/scripts/smoke_dialogue_llm_action_commit_lan.sh

  echo
  echo "== 3) WS hello -> placeholder remplacé + commit + snapshot corrélé =="
  LBG_SMOKE_TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-410}" bash infra/scripts/smoke_ws_hello_llm_aid_lan.sh
else
  echo
  echo "SKIP: smokes LLM (RUN_LLM=0)"
fi

echo
echo "OK: smoke_lan_ci"

