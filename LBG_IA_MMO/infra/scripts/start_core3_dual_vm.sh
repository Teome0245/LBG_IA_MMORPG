#!/usr/bin/env bash
# Démarre Core3 sur la VM MMO.
# Par défaut : Prime seul (PreCu coupé pour stabilité / pont IA).
# Pour les deux : CORE3_START_PRECU=1 bash infra/scripts/start_core3_dual_vm.sh
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
START_PRECU="${CORE3_START_PRECU:-0}"

if [[ "${START_PRECU}" != "1" ]]; then
  exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start_core3_prime_only_vm.sh"
fi

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_core3_dual_%r@%h:%p")

echo "=== Démarrage dual Core3 (PreCu + Prime) sur ${VM_USER}@${VM_HOST} ==="

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail

start_one() {
  local name="$1"
  local dir="$2"
  local bin="$3"
  local log="/tmp/core3-${name}.log"
  local pidfile="/tmp/core3-${name}.pid"

  if [[ ! -x "${dir}/${bin}" ]]; then
    echo "ERROR: binaire absent : ${dir}/${bin}" >&2
    return 1
  fi

  pkill -x "${bin}" 2>/dev/null || true
  sleep 1

  cd "${dir}"
  nohup "./${bin}" > "${log}" 2>&1 &
  echo $! > "${pidfile}"
  echo "${name}: ./${bin} PID $(cat "${pidfile}") log ${log}"
}

# Arrêt de l’ancien processus générique « core3 » (avant dual-instance)
pkill -x core3 2>/dev/null || true
sleep 2

start_one swgemu /opt/lbg-new-mmo/MMOCoreORB/bin core3-swgemu
start_one clean  /opt/lbg-new-mmo-clean/MMOCoreORB/bin core3-clean

sleep 2
echo "--- Processus ---"
pgrep -a 'core3' || true
echo "--- Ports UDP ---"
ss -ulnp 2>/dev/null | grep core3 || true
EOF

echo "=== Les deux instances démarrent (boot ~1–3 min chacune) ==="
echo "  Logs : ssh ${VM_USER}@${VM_HOST} 'tail -f /tmp/core3-swgemu.log'  (stock)"
echo "         ssh ${VM_USER}@${VM_HOST} 'tail -f /tmp/core3-clean.log'   (Antigravity)"
