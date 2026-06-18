#!/usr/bin/env bash
# Watchdog infra LAN (VM core 140) — Proxmox + mémoire 140/245/110, Prime exclu par défaut.
# Usage : bash infra/scripts/run_infra_watchdog.sh [--json]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JSON_OUT=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON_OUT=1 ;;
  esac
done

export PYTHONPATH="${ROOT_DIR}/agents/src${PYTHONPATH:+:${PYTHONPATH}}"

PY="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY="python3"
fi

if [[ "${JSON_OUT}" == "1" ]]; then
  exec "${PY}" -m lbg_agents.infra_watchdog
fi

"${PY}" -m lbg_agents.infra_watchdog
rc=$?
exit "${rc}"
