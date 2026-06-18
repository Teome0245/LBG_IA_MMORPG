#!/usr/bin/env bash
# Arrête l'instance PreCu (core3-swgemu) sur la VM MMO — libère CPU/RAM pour Prime + pont IA.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Arrêt PreCu (core3-swgemu) sur ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
pkill -x core3-swgemu 2>/dev/null || true
sleep 1
mkdir -p /home/lbg/.config/lbg
touch /home/lbg/.config/lbg/core3-precu-disabled
if pgrep -x core3-swgemu >/dev/null; then
  echo "WARN: core3-swgemu encore actif" >&2
  pgrep -a core3-swgemu
  exit 1
fi
echo "PreCu arrêté (flag ~/.config/lbg/core3-precu-disabled)"
pgrep -a core3-clean 2>/dev/null && echo "Prime (core3-clean) toujours actif" || echo "Prime non démarré"
EOF
