#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -U pip

"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/agents[dialogue_http_service]"
"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/backend"
"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/orchestrator"
if [ "${LBG_SKIP_MMO_SERVER:-0}" = "1" ]; then
  echo "Skip mmo_server (LBG_SKIP_MMO_SERVER=1 — déploiement core sans slice MMO sur cet hôte)"
else
  "${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmo_server"
fi

if [ "${LBG_SKIP_MMMORPG_WS:-0}" = "1" ]; then
  echo "Skip mmmorpg_server WebSocket (LBG_SKIP_MMMORPG_WS=1)"
else
  "${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmmorpg_server"
fi

echo "Installed into ${VENV_DIR}"

