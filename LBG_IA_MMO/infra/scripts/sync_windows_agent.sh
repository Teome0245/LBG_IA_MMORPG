#!/usr/bin/env bash
set -euo pipefail

# Sync du module Windows Agent_IA vers C:\Agent_IA (WSL).
#
# Usage:
#   bash LBG_IA_MMO/infra/scripts/sync_windows_agent.sh
#
# Prérequis:
# - WSL avec montage /mnt/c

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/windows_agent/Agent_IA"
DST="/mnt/c/Agent_IA"

if [ ! -d "$SRC" ]; then
  echo "ERREUR: source introuvable: $SRC" >&2
  exit 1
fi
if [ ! -d "/mnt/c" ]; then
  echo "ERREUR: /mnt/c introuvable (WSL?)" >&2
  exit 1
fi

mkdir -p "$DST"

# Copie "miroir" des fichiers de code/doc.
cp -f "$SRC/main.py" "$DST/main.py"
cp -f "$SRC/executor.py" "$DST/executor.py"
cp -f "$SRC/models.py" "$DST/models.py"
cp -f "$SRC/program_resolver.py" "$DST/program_resolver.py"
cp -f "$SRC/requirements.txt" "$DST/requirements.txt"
cp -f "$SRC/run_agent.cmd" "$DST/run_agent.cmd"
cp -f "$SRC/desktop.env.example" "$DST/desktop.env.example"

# Ne pas écraser `desktop.env` utilisateur s’il existe déjà.
if [ ! -f "$DST/desktop.env" ]; then
  cp -f "$SRC/desktop.env" "$DST/desktop.env"
fi

echo "OK: sync -> $DST"

