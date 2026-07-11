#!/usr/bin/env bash
# Sync artefacts client Godot live (SOE + ZB-0) vers VM core 140.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NEW_MMO="${LBG_NEW_MMO_ROOT:-/home/sdesh/projects/new_mmo}"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
REMOTE_ROOT="${LBG_REMOTE_NEW_MMO_ROOT:-/opt/new_mmo}"

echo "=== Sync client tracks → ${VM_USER}@${VM_HOST}:${REMOTE_ROOT} ==="
[[ -d "${NEW_MMO}/client-prime-lbg" ]] || { echo "client-prime-lbg absent: ${NEW_MMO}" >&2; exit 1; }

ssh "${VM_USER}@${VM_HOST}" "sudo mkdir -p ${REMOTE_ROOT}/client-prime-lbg ${REMOTE_ROOT}/lbg-mmo/server-core3/server/lbg && sudo chown -R ${VM_USER}:${VM_USER} ${REMOTE_ROOT}"
rsync -a --delete \
  "${NEW_MMO}/client-prime-lbg/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/client-prime-lbg/"
if [[ -f "${NEW_MMO}/lbg-mmo/server-core3/server/lbg/LbgZoneBridge.h" ]]; then
  scp -q \
    "${NEW_MMO}/lbg-mmo/server-core3/server/lbg/LbgZoneBridge.h" \
    "${NEW_MMO}/lbg-mmo/server-core3/server/lbg/LbgZoneBridge.cpp" \
    "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/lbg-mmo/server-core3/server/lbg/"
fi
echo "OK — sur 140, définir dans /etc/lbg-ia-mmo.env :"
echo "  LBG_NEW_MMO_ROOT=${REMOTE_ROOT}"
echo "  LBG_CLIENT_PRIME_LBG_DIR=${REMOTE_ROOT}/client-prime-lbg"
