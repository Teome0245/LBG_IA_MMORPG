#!/usr/bin/env bash
# Redémarre Serveur Prime (core3-clean) — systemd si installé, sinon nohup legacy.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CLEAN_BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
BIN="core3-clean"
LOG="/tmp/core3-clean.log"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
DIR="${CLEAN_BIN}"
BIN="${BIN}"
LOG="${LOG}"

if [[ ! -x "\${DIR}/\${BIN}" ]]; then
  echo "ERROR: binaire absent : \${DIR}/\${BIN}" >&2
  exit 1
fi

use_systemd=0
if [[ -f /etc/systemd/system/lbg-core3-prime.service ]]; then
  if systemctl is-enabled lbg-core3-prime.service &>/dev/null; then
    use_systemd=1
  fi
fi

if [[ "\${use_systemd}" == "1" ]]; then
  echo "Prime: systemctl restart lbg-core3-prime.service"
  sudo systemctl restart lbg-core3-prime.service
  sleep 2
  systemctl show lbg-core3-prime.service -p ActiveState,SubState,MainPID --no-pager
  pgrep -a core3-clean || { echo "ERROR: core3-clean absent apres restart systemd" >&2; exit 1; }
else
  echo "WARN: lbg-core3-prime.service non active — fallback nohup"
  echo "  Installez : bash infra/scripts/install_core3_prime_systemd_vm.sh"
  pkill -x "\${BIN}" 2>/dev/null || true
  pkill -x core3-swgemu 2>/dev/null || true
  sleep 2
  cd "\${DIR}"
  nohup "./\${BIN}" >> "\${LOG}" 2>&1 </dev/null &
  disown || true
  sleep 2
  pgrep -a "\${BIN}" || { echo "ERROR: \${BIN} absent apres nohup" >&2; exit 1; }
fi
EOF
