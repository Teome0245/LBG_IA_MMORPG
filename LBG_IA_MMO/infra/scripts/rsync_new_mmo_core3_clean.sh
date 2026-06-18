#!/usr/bin/env bash
# Sync MMOCoreORB (build Antigravity) vers l’instance « clean » uniquement — ne touche pas le stock SWGEmu.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REL="${LBG_NEW_MMO_REL_PATH:-lbg-mmo/Core3/MMOCoreORB}"

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SERVICE_USER="${LBG_NEW_MMO_VM_SERVICE_USER:-${VM_USER}}"

REMOTE_STAGE="/home/${VM_USER}/.deploy/new_mmo/MMOCoreORB-clean"
REMOTE_DIR="/opt/lbg-new-mmo-clean/MMOCoreORB"

if [[ -n "${LBG_NEW_MMO_REPO:-}" ]]; then
  NEW_MMO_REPO="$(cd "${LBG_NEW_MMO_REPO}" && pwd)"
else
  NEW_MMO_REPO=""
  for _cand in "${ROOT_DIR}/../../new_mmo" "${ROOT_DIR}/../new_mmo"; do
    if [[ -d "${_cand}/${REL}" ]]; then
      NEW_MMO_REPO="$(cd "${_cand}" && pwd)"
      break
    fi
  done
fi

LOCAL_SRC="${NEW_MMO_REPO}/${REL}"

# Aligner le binaire CMake (lbg-mmo/bin) vers MMOCoreORB/bin avant rsync
if [[ -f "${NEW_MMO_REPO}/lbg-mmo/bin/core3" ]]; then
  cp -a "${NEW_MMO_REPO}/lbg-mmo/bin/core3" "${LOCAL_SRC}/bin/core3-clean" 2>/dev/null \
    || sudo cp -a "${NEW_MMO_REPO}/lbg-mmo/bin/core3" "${LOCAL_SRC}/bin/core3-clean"
fi

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_new_mmo_clean_%r@%h:%p"
)

RSYNC_EXCLUDES=(
  --exclude 'bin/databases/'
  --exclude 'bin/log/'
  --exclude 'bin/boot.log'
  --exclude 'bin/conf/config-local.lua'
)

if [[ ! -d "${LOCAL_SRC}" ]]; then
  echo "ERROR: source introuvable : ${LOCAL_SRC}" >&2
  exit 1
fi

echo "=== rsync Core3 CLEAN → ${VM_HOST} ==="
echo "LOCAL : ${LOCAL_SRC}/"
echo "FINAL : ${REMOTE_DIR}/"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "mkdir -p '${REMOTE_STAGE}'"

rsync -avz --progress "${RSYNC_EXCLUDES[@]}" -e "ssh ${SSH_OPTS[*]}" \
  "${LOCAL_SRC}/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"

ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  sudo mkdir -p \"${REMOTE_DIR}\"
  sudo rsync -a ${RSYNC_EXCLUDES[*]} \"${REMOTE_STAGE}/\" \"${REMOTE_DIR}/\"
  sudo chown -R ${SERVICE_USER}:${SERVICE_USER} /opt/lbg-new-mmo-clean
  echo OK: ${REMOTE_DIR}
'"

echo "=== terminé (instance stock /opt/lbg-new-mmo non modifiée par ce script) ==="
