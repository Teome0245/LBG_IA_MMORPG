#!/usr/bin/env bash
# Démarre uniquement Serveur Prime (core3-clean) — PreCu laissé arrêté (stabilité / pont IA).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

bash "${ROOT_DIR}/infra/scripts/stop_core3_precu_vm.sh"

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_core3_dual_%r@%h:%p")

echo "=== Démarrage Prime seul (core3-clean) sur ${VM_USER}@${VM_HOST} ==="

bash "${ROOT_DIR}/infra/scripts/restart_core3_prime_vm.sh"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" \
  'pgrep -x core3-swgemu && echo "WARN: PreCu encore actif" || echo "PreCu arrêté (OK)"'

echo "Boot Prime ~2–3 min — pastille verte sur http://${VM_HOST}:8792/"
echo "systemd : bash infra/scripts/install_core3_prime_systemd_vm.sh (redémarrage auto)"
