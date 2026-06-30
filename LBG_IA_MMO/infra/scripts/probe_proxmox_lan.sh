#!/usr/bin/env bash
# Sonde Proxmox LAN : version API, nœuds, permissions time/VM, accès SSH.
# Ne modifie rien — sûr pendant un build VM.
#
# Usage :
#   bash infra/scripts/probe_proxmox_lan.sh
#   LBG_PROXMOX_HOST=192.168.0.201 bash infra/scripts/probe_proxmox_lan.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/agents/src:${PYTHONPATH:-}"

PY="${ROOT_DIR}/agents/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY=python3
fi

if [[ -f "${ROOT_DIR}/infra/secrets/lbg.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/infra/secrets/lbg.env"
  set +a
fi

"${PY}" - <<'PY'
import json
import os
import subprocess

from lbg_agents.proxmox_client import probe_all_proxmox_hosts, proxmox_configured, proxmox_hosts

ssh_user = os.environ.get("LBG_PROXMOX_SSH_USER", "root").strip() or "root"
out = {
    "configured": proxmox_configured(),
    "hosts": proxmox_hosts(),
    "api": probe_all_proxmox_hosts(),
    "ssh": [],
}

for host in proxmox_hosts():
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        f"{ssh_user}@{host}",
        "timedatectl status 2>/dev/null | head -8; pveversion 2>/dev/null | head -1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        out["ssh"].append(
            {
                "host": host,
                "user": ssh_user,
                "ok": proc.returncode == 0,
                "stdout": (proc.stdout or "").strip(),
                "stderr": (proc.stderr or "").strip()[:300],
            }
        )
    except Exception as exc:
        out["ssh"].append({"host": host, "user": ssh_user, "ok": False, "error": str(exc)})

print(json.dumps(out, ensure_ascii=False, indent=2))
PY
