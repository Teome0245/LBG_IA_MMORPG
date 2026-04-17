#!/usr/bin/env bash
set -euo pipefail

# Reset état persisté `mmo_server` sur une VM (LAN) pour forcer le rechargement du seed.
#
# Pourquoi : un simple `systemctl restart lbg-mmo-server` peut recréer `world_state.json` à l’arrêt
# (sauvegarde finale), empêchant le seed d’être rechargé au boot suivant.
#
# Usage:
#   LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg bash infra/scripts/reset_mmo_state_vm.sh
#
# Variables :
#   LBG_VM_HOST     défaut 192.168.0.245
#   LBG_VM_USER     défaut lbg
#   LBG_MMO_UNIT    défaut lbg-mmo-server
#   LBG_MMO_STATE_PATH optionnel (sinon : /opt/LBG_IA_MMO/mmo_server/data/world_state.json)
#

VM_HOST="${LBG_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_VM_USER:-lbg}"
UNIT="${LBG_MMO_UNIT:-lbg-mmo-server}"
STATE_PATH="${LBG_MMO_STATE_PATH:-}"

ssh -o BatchMode=yes -o ConnectTimeout=4 "${VM_USER}@${VM_HOST}" "bash -s" <<'EOS'
set -euo pipefail

UNIT="${LBG_MMO_UNIT:-lbg-mmo-server}"
STATE_PATH="${LBG_MMO_STATE_PATH:-}"

if [ -z "${STATE_PATH}" ]; then
  STATE_PATH="/opt/LBG_IA_MMO/mmo_server/data/world_state.json"
fi

echo "Reset mmo_server state on $(hostname) — unit=${UNIT} state=${STATE_PATH}"

echo "Stopping ${UNIT}…"
sudo -n systemctl stop "${UNIT}" || true

# Attendre l’arrêt effectif (évite la sauvegarde finale qui recrée le state).
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if sudo -n systemctl is-active --quiet "${UNIT}"; then
    sleep 0.5
  else
    break
  fi
done

if sudo -n systemctl is-active --quiet "${UNIT}"; then
  echo "ERREUR: ${UNIT} encore actif après stop" >&2
  exit 1
fi

if [ -f "${STATE_PATH}" ]; then
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  sudo -n mv "${STATE_PATH}" "${STATE_PATH}.bak.${ts}"
  echo "Moved -> ${STATE_PATH}.bak.${ts}"
else
  echo "No state file to move (ok)"
fi

echo "Starting ${UNIT}…"
sudo -n systemctl start "${UNIT}"
sudo -n systemctl is-active --quiet "${UNIT}"
echo "${UNIT}: active"
EOS

