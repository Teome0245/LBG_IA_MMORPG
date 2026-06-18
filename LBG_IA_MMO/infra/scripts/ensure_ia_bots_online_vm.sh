#!/usr/bin/env bash
# Reconnecte Lia + Nix sur Prime (246) sans redemarrer le serveur.
# Usage : bash infra/scripts/ensure_ia_bots_online_vm.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_VM_USER:-lbg}"

ssh "${VM_USER}@${VM_HOST}" "bash -lc '
  set -a
  [[ -f /etc/lbg-ia-mmo.env ]] && . /etc/lbg-ia-mmo.env
  [[ -f /etc/lbg-core3-ia.env ]] && . /etc/lbg-core3-ia.env
  set +a
  export PYTHONPATH=/opt/LBG_IA_MMO/agents/src
  export LBG_CORE3_IA_SIDECAR_URL=http://127.0.0.1:8791
  export LBG_CORE3_BOT_AUTO_CONNECT=1
  /usr/bin/python3 - <<\"PY\"
from lbg_agents.core3_bot_connection import ensure_ia_bots_online
import json
print(json.dumps(ensure_ia_bots_online(), ensure_ascii=False, indent=2))
PY
'"
