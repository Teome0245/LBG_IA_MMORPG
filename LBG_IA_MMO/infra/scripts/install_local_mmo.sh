#!/usr/bin/env bash
# Installation minimale : paquet mmo_server uniquement (VM dédiée MMO, ex. 0.245).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -U pip
"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmo_server"

if [ "${LBG_DEPLOY_MMMORPG_WS:-0}" = "1" ]; then
  echo "WARN: install mmmorpg_server (décommissionné — opt-in LBG_DEPLOY_MMMORPG_WS=1)"
  "${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmmorpg_server"
else
  echo "Skip mmmorpg_server (décommissionné — ADR 0012). Opt-in : LBG_DEPLOY_MMMORPG_WS=1"
fi

# Boucles Lia / joueurs IA (lbg-core3-ia-lia-autonomy, player-autonomy@)
if [ -f "${ROOT_DIR}/agents/pyproject.toml" ]; then
  "${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/agents"
fi

echo "Installed mmo_server into ${VENV_DIR} (mmmorpg_server only if LBG_DEPLOY_MMMORPG_WS=1)"
