#!/usr/bin/env bash
# Installation minimale : paquet mmo_server uniquement (VM dédiée MMO, ex. 0.245).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -U pip
"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmo_server"

if [ "${LBG_SKIP_MMMORPG_WS:-0}" != "1" ]; then
  "${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}/mmmorpg_server"
fi

echo "Installed mmo_server (and mmmorpg_server unless LBG_SKIP_MMMORPG_WS=1) into ${VENV_DIR}"
