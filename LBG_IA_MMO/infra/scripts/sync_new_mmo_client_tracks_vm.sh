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

ssh "${VM_USER}@${VM_HOST}" "sudo mkdir -p \
  ${REMOTE_ROOT}/client-prime-lbg \
  ${REMOTE_ROOT}/lbg-mmo/server-core3/server/lbg \
  ${REMOTE_ROOT}/lbg-mmo/server-core3/server/zone \
  && sudo chown -R ${VM_USER}:${VM_USER} ${REMOTE_ROOT}"
rsync -a --delete \
  "${NEW_MMO}/client-prime-lbg/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/client-prime-lbg/"
if [[ -d "${NEW_MMO}/lbg-mmo/server-core3/server/lbg" ]]; then
  rsync -a --delete \
    "${NEW_MMO}/lbg-mmo/server-core3/server/lbg/" \
    "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/lbg-mmo/server-core3/server/lbg/"
fi
ZB0_ZONE_IMPL="${NEW_MMO}/lbg-mmo/server-core3/server/zone/ZoneServerImplementation.cpp"
ZB0_CMAKE="${NEW_MMO}/lbg-mmo/server-core3/CMakeLists.txt"
if [[ -f "${ZB0_ZONE_IMPL}" ]]; then
  scp -q "${ZB0_ZONE_IMPL}" "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/lbg-mmo/server-core3/server/zone/"
fi
if [[ -f "${ZB0_CMAKE}" ]]; then
  scp -q "${ZB0_CMAKE}" "${VM_USER}@${VM_HOST}:${REMOTE_ROOT}/lbg-mmo/server-core3/"
fi
echo "OK — sur 140, définir dans /etc/lbg-ia-mmo.env :"
echo "  LBG_NEW_MMO_ROOT=${REMOTE_ROOT}"
echo "  LBG_CLIENT_PRIME_LBG_DIR=${REMOTE_ROOT}/client-prime-lbg"
