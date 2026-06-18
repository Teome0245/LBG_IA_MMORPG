#!/usr/bin/env bash
set -euo pipefail

# Synchronise l’arborescence Core3 / SWGEmu **MMOCoreORB** (repo new_mmo) vers la VM MMO dédiée.
# Ce dépôt est distinct du slice Python `mmo_server` / `mmmorpg_server` (déployé via deploy_vm.sh rôle mmo, ex. 245).
# Doc associée : docs/core3_mmoorb_vm.md (build, lancement core3, clarification login3).
#
# Usage (depuis la machine de dev, avec les sources locales) :
#   cd LBG_IA_MMO && bash infra/scripts/rsync_new_mmo_core3_orb.sh
#
# Variables (optionnelles) :
#   LBG_NEW_MMO_VM_HOST       défaut : 192.168.0.245 (VM MMO LAN ; pas de lien avec une box type Freebox)
#   LBG_NEW_MMO_VM_USER       défaut : lbg
#   LBG_NEW_MMO_VM_SERVICE_USER  défaut : même que LBG_NEW_MMO_VM_USER
#   LBG_NEW_MMO_REPO          défaut : auto — ../../new_mmo puis ../new_mmo (depuis LBG_IA_MMO)
#   LBG_NEW_MMO_REL_PATH      défaut : lbg-mmo/Core3/MMOCoreORB
#   LBG_NEW_MMO_REMOTE_DIR    défaut : /opt/lbg-new-mmo/MMOCoreORB   (cible finale, propriétaire service)
#   LBG_NEW_MMO_RSYNC_DELETE  défaut : 0 — si 1, ajoute --delete au rsync final
#
# Exemple équivalent à ta commande, avec destination corrigée (chemin absolu + /opt) :
#   rsync -avz --progress \
#     /home/sdesh/projects/new_mmo/lbg-mmo/Core3/MMOCoreORB/ \
#     lbg@192.168.0.245:/home/lbg/.deploy/new_mmo/MMOCoreORB/
#   puis promotion sudo vers /opt/lbg-new-mmo/MMOCoreORB (fait par ce script).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SERVICE_USER="${LBG_NEW_MMO_VM_SERVICE_USER:-${VM_USER}}"
REL="${LBG_NEW_MMO_REL_PATH:-lbg-mmo/Core3/MMOCoreORB}"

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

REMOTE_STAGE="/home/${VM_USER}/.deploy/new_mmo/MMOCoreORB"
REMOTE_DIR="${LBG_NEW_MMO_REMOTE_DIR:-/opt/lbg-new-mmo/MMOCoreORB}"

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_new_mmo_%r@%h:%p"
)

if [[ ! -d "${LOCAL_SRC}" ]]; then
  echo "ERROR: source introuvable : ${LOCAL_SRC}" >&2
  echo "       Ajuste LBG_NEW_MMO_REPO ou clone new_mmo à côté de LBG_IA_MMO." >&2
  exit 1
fi

RSYNC_BASE=(rsync -avz --progress -e "ssh ${SSH_OPTS[*]}")

echo "=== new_mmo Core3 MMOCoreORB ==="
echo "LOCAL : ${LOCAL_SRC}/"
echo "STAGE : ${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"
echo "FINAL : ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/ (via sudo)"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc 'set -euo pipefail; mkdir -p \"${REMOTE_STAGE}\"'"

"${RSYNC_BASE[@]}" \
  "${LOCAL_SRC}/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"

DELETE_FLAG=()
if [[ "${LBG_NEW_MMO_RSYNC_DELETE:-0}" == "1" ]]; then
  DELETE_FLAG=(--delete)
fi

# shellcheck disable=SC2029
ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  sudo -n mkdir -p \"$(dirname "${REMOTE_DIR}")\"
  sudo -n mkdir -p \"${REMOTE_DIR}\"
  sudo -n rsync -a ${DELETE_FLAG[*]} \"${REMOTE_STAGE}/\" \"${REMOTE_DIR}/\"
  sudo -n chown -R ${SERVICE_USER}:${SERVICE_USER} \"${REMOTE_DIR}\"
  echo OK: arborescence sous ${REMOTE_DIR}
'"

echo "=== terminé ==="
