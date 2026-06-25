#!/usr/bin/env bash
# Compile server-core3 (Antigravity) sur la VM, installe core3-clean, optionnellement sync avant.
#
# Usage :
#   bash infra/scripts/build_core3_antigravity_vm.sh           # build seul
#   bash infra/scripts/build_core3_antigravity_vm.sh --sync    # rsync puis build
#   bash infra/scripts/build_core3_antigravity_vm.sh --sync --start  # + démarrage instance clean
#
# Variables : LBG_NEW_MMO_VM_HOST, LBG_ANTIGRAVITY_REMOTE, LBG_CLEAN_RUNTIME_BIN
#
# Avant build : bash infra/scripts/check_proxmox_storage_lan.sh
# Après build  : bash infra/scripts/prime_disk_hygiene_vm.sh
# Doc          : docs/runbook_proxmox_storage_prime.md

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SRC_DIR="${LBG_ANTIGRAVITY_REMOTE:-/opt/lbg-antigravity/lbg-mmo}"
RUNTIME_BIN="${LBG_CLEAN_RUNTIME_BIN:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
BUILD_LOG="/tmp/core3-antigravity-build.log"

DO_SYNC=0
DO_START=0
for arg in "$@"; do
  case "$arg" in
    --sync) DO_SYNC=1 ;;
    --start) DO_START=1 ;;
  esac
done

if [[ "${DO_SYNC}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/rsync_lbg_mmo_antigravity_vm.sh"
fi

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_antigravity_%r@%h:%p")

echo "=== Build Antigravity server-core3 sur ${VM_USER}@${VM_HOST} ==="

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail

SRC="${SRC_DIR}"
BIN="${RUNTIME_BIN}"
LOG="${BUILD_LOG}"

# Arrêter l’ancien build MMOCoreORB (mauvais arbre de sources)
pkill -f '/opt/lbg-new-mmo-clean/MMOCoreORB/build' 2>/dev/null || true
pkill -f 'cmake --build.*MMOCoreORB/build' 2>/dev/null || true
sleep 1

if [[ ! -d "\${SRC}/server-core3" ]]; then
  echo "ERROR: sources absentes : \${SRC} — lancer avec --sync" >&2
  exit 1
fi

mkdir -p "\${SRC}/bin" "\${BIN}/databases" "\${BIN}/log"
touch "\${BIN}/log/core3.log"

if [[ ! -f "\${BIN}/conf/config-local.lua" ]]; then
  echo "WARN: \${BIN}/conf/config-local.lua absent — exécuter setup_core3_dual_vm.sh" >&2
fi

rm -rf "\${SRC}/build"
mkdir -p "\${SRC}/build"
cd "\${SRC}/build"

if ! test -f /usr/include/gmock/gmock.h; then
  echo "Installation libgmock-dev (headers gmock pour autogen COMPILE_TESTS)…"
  sudo apt-get install -y -qq libgmock-dev google-mock >/dev/null 2>&1 || true
fi

echo "CMake configure…"
# BUILD_IDL=ON : lie les .cpp autogen (sinon idlobjects ne prend que server-core3/src/*.cpp → linker errors)
cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_NATIVE=OFF -DBUILD_IDL=ON .. > "\${LOG}" 2>&1

echo "Pre-creating autogen object directories…"
if [[ -d "\${SRC}/server-core3/autogen" ]]; then
  cd "\${SRC}/server-core3/autogen"
  find . -type d -exec mkdir -p "\${SRC}/build/server-core3/CMakeFiles/idlobjects.dir/autogen/{}" \;
  cd "\${SRC}/build"
fi

echo "Compilation (arrière-plan) — journal : \${LOG}"
nohup cmake --build . -j"\$(nproc)" --target core3 >> "\${LOG}" 2>&1 &
echo "Build PID: \$!"

sleep 2
tail -5 "\${LOG}"
EOF

echo ""
echo "Suivi : ssh ${VM_USER}@${VM_HOST} 'tail -f ${BUILD_LOG}'"
echo "Fin de build : bash ${ROOT_DIR}/infra/scripts/install_core3_clean_after_vm_build.sh"
if [[ "${DO_START}" == "1" ]]; then
  echo "(avec --start : install lancera aussi core3-clean)"
fi

if [[ "${DO_START}" == "1" ]]; then
  echo ""
  echo "Note : --start ne peut démarrer qu’après la fin du build — relancer install après [100%]."
fi
