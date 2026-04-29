#!/usr/bin/env bash
set -euo pipefail

# Sync du module Linux Agent_IA vers une VM (à utiliser plus tard).
#
# Usage:
#   LBG_VM_HOST=192.168.0.140 bash LBG_IA_MMO/infra/scripts/sync_linux_agent_vm.sh
#
# Copie le code dans /opt/LBG_IA_MMO/linux_agent/Agent_IA.
# Ne crée pas de service systemd automatiquement.

HOST="${LBG_VM_HOST:-}"
if [ -z "$HOST" ]; then
  echo "ERREUR: définir LBG_VM_HOST (ex. 192.168.0.140)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/linux_agent/Agent_IA"

if [ ! -d "$SRC" ]; then
  echo "ERREUR: source introuvable: $SRC" >&2
  exit 1
fi

echo "Sync Linux Agent_IA -> lbg@$HOST:/opt/LBG_IA_MMO/linux_agent/Agent_IA"
rsync -av --delete \
  --exclude "__pycache__/" \
  --exclude ".venv/" \
  --exclude "*.pyc" \
  "$SRC/" "lbg@$HOST:/opt/LBG_IA_MMO/linux_agent/Agent_IA/"

echo "OK"

