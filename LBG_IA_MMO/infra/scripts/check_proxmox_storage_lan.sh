#!/usr/bin/env bash
# Sonde pool LVM thin Proxmox (local-lvm) — prévention io-error VM Prime.
#
# Usage :
#   bash infra/scripts/check_proxmox_storage_lan.sh
#   bash infra/scripts/check_proxmox_storage_lan.sh --json
#   LBG_PROXMOX_SSH_HOST=192.168.0.200 bash infra/scripts/check_proxmox_storage_lan.sh
#
# Codes sortie : 0 OK, 1 warn, 2 critical, 3 erreur sonde

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/agents/src${PYTHONPATH:+:${PYTHONPATH}}"

PY="${LBG_PYTHON:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PY="${ROOT_DIR}/.venv/bin/python"
  else
    PY="python3"
  fi
fi

exec "${PY}" -m lbg_agents.proxmox_storage_probe "$@"
