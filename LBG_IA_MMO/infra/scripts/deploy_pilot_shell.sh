#!/usr/bin/env bash
# Build pilot_shell → pilot_web/v2/ (servi sous /pilot/v2/ par FastAPI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SHELL_DIR="${ROOT}/pilot_shell"
OUT_DIR="${ROOT}/pilot_web/v2"

echo "[deploy_pilot_shell] build depuis ${SHELL_DIR}"
cd "${SHELL_DIR}"

if [[ ! -d node_modules ]]; then
  npm install
fi

npm run build

if [[ ! -f "${OUT_DIR}/index.html" ]]; then
  echo "[deploy_pilot_shell] ERREUR : index.html absent dans ${OUT_DIR}" >&2
  exit 1
fi

echo "[deploy_pilot_shell] OK → ${OUT_DIR}"
echo "  Ouvrir : http://127.0.0.1:8000/pilot/v2/"
