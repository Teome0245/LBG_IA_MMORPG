#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-ci}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install -U pip

python -m pip install \
  -e ./backend \
  -e ./orchestrator \
  -e ./agents \
  -e ./mmo_server \
  -e ./mmmorpg_server

python -m pip install -U pytest pytest-asyncio

pytest -q
