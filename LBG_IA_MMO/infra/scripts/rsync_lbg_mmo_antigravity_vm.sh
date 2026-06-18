#!/usr/bin/env bash
# Synchronise l’arborescence Antigravity lbg-mmo (server-core3 + MMOEngine) vers la VM MMO.
# N’envoie pas Core3/MMOCoreORB entier ni les builds locaux — conf runtime séparé.
#
# Usage (depuis LBG_IA_MMO/) :
#   bash infra/scripts/rsync_lbg_mmo_antigravity_vm.sh
#
# Variables :
#   LBG_NEW_MMO_VM_HOST     défaut 192.168.0.245
#   LBG_NEW_MMO_VM_USER     défaut lbg
#   LBG_NEW_MMO_REPO        défaut auto (../../new_mmo ou ../new_mmo)
#   LBG_ANTIGRAVITY_REMOTE  défaut /opt/lbg-antigravity/lbg-mmo
#   LBG_CLEAN_RUNTIME_BIN   défaut /opt/lbg-new-mmo-clean/MMOCoreORB/bin (conf + databases)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REL="lbg-mmo"

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
REMOTE_DIR="${LBG_ANTIGRAVITY_REMOTE:-/opt/lbg-antigravity/lbg-mmo}"
RUNTIME_BIN="${LBG_CLEAN_RUNTIME_BIN:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
REMOTE_STAGE="/home/${VM_USER}/.deploy/lbg-antigravity/lbg-mmo"

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
CONF_SRC="${NEW_MMO_REPO}/${REL}/Core3/MMOCoreORB/bin/conf"

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_antigravity_%r@%h:%p"
)

# /build/ = uniquement lbg-mmo/build (pas MMOEngine/build/cmake/…)
RSYNC_EXCLUDES=(
  --exclude '/build/'
  --exclude '/server-core3/build/'
  --exclude '/bin/'
  --exclude '/engine3/'
  --exclude '/Core3/'
  --exclude '/archives_swg/'
  --exclude '/.git/'
)

if [[ ! -d "${LOCAL_SRC}/server-core3" ]] || [[ ! -d "${LOCAL_SRC}/MMOEngine" ]]; then
  echo "ERROR: ${LOCAL_SRC} incomplet (server-core3 ou MMOEngine manquant)." >&2
  exit 1
fi

echo "=== rsync lbg-mmo Antigravity ==="
echo "LOCAL  : ${LOCAL_SRC}/"
echo "STAGE  : ${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"
echo "FINAL  : ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/"
echo "CONF   : ${CONF_SRC}/ → ${RUNTIME_BIN}/conf/ (sans config-local.lua)"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "mkdir -p '${REMOTE_STAGE}'"

rsync -avz --progress "${RSYNC_EXCLUDES[@]}" -e "ssh ${SSH_OPTS[*]}" \
  "${LOCAL_SRC}/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"

# shellcheck disable=SC2029
ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  sudo mkdir -p /opt/lbg-antigravity
  sudo rsync -a ${RSYNC_EXCLUDES[*]} \"${REMOTE_STAGE}/\" \"${REMOTE_DIR}/\"
  sudo chown -R ${VM_USER}:${VM_USER} /opt/lbg-antigravity
  mkdir -p \"${REMOTE_DIR}/bin\"
'"

if [[ -d "${CONF_SRC}" ]]; then
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "mkdir -p '${RUNTIME_BIN}/conf'"
  rsync -avz -e "ssh ${SSH_OPTS[*]}" \
    --exclude 'config-local.lua' \
    "${CONF_SRC}/" \
    "${VM_USER}@${VM_HOST}:${RUNTIME_BIN}/conf/"
fi

echo "=== terminé ==="
