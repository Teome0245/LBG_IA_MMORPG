#!/usr/bin/env bash
# Envoie le prompt de contexte non-MMO à Claude sur 140 (mode -p, non interactif).
#
# Usage (depuis WSL) :
#   bash infra/scripts/claude_140_inject_context.sh
#
# Usage (sur 140) :
#   cd /opt/LBG_IA_MMO && bash infra/scripts/claude_140_inject_context.sh
#
# Le prompt complet est dans docs/prompt_claude_140_non_mmo.txt

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPT_FILE="${ROOT}/docs/prompt_claude_140_non_mmo.txt"
LAUNCHER="${ROOT}/infra/scripts/claude_ollama_lan.sh"
CORE_HOST="${LBG_LAN_HOST_CORE:-192.168.0.140}"
VM_USER="${LBG_VM_USER:-lbg}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[claude_140_inject] ERREUR : ${PROMPT_FILE} absent" >&2
  exit 1
fi

run_local() {
  cd "$ROOT"
  exec bash "$LAUNCHER" -p "$(cat "$PROMPT_FILE")"
}

run_remote() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ "$ip" == "$CORE_HOST" ]]; then
    run_local
    return
  fi
  ssh -o BatchMode=yes -o ConnectTimeout=8 "${VM_USER}@${CORE_HOST}" bash -s <<EOF
set -euo pipefail
cd ${ROOT}
test -f docs/prompt_claude_140_non_mmo.txt || { echo "prompt absent sur 140 — deploy d'abord"; exit 1; }
bash infra/scripts/claude_ollama_lan.sh -p "\$(cat docs/prompt_claude_140_non_mmo.txt)"
EOF
}

# Si on est déjà sur 140 avec le bon chemin
if [[ -d "$ROOT/backend" && "$(hostname -I 2>/dev/null | awk '{print $1}')" == "$CORE_HOST" ]]; then
  run_local
else
  run_remote
fi
