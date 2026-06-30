#!/usr/bin/env bash
# Aligne le fuseau Proxmox VE sur Europe/Paris (hôte hyperviseur uniquement).
# Sûr pendant un build cmake dans une VM : ne redémarre ni n'arrête les VM.
#
# Prérequis : accès SSH root (ou sudo) sur chaque nœud Proxmox.
#   ssh-copy-id root@192.168.0.201
#
# Usage (défaut 192.168.0.201) :
#   bash infra/scripts/set_proxmox_timezone_europe_paris.sh
#
# Plusieurs hyperviseurs (optionnel) :
#   LBG_PROXMOX_SSH_HOSTS=192.168.0.201,192.168.0.202 bash infra/scripts/set_proxmox_timezone_europe_paris.sh
#
# Dry-run (affiche sans appliquer) :
#   LBG_PROXMOX_TZ_DRY_RUN=1 bash infra/scripts/set_proxmox_timezone_europe_paris.sh

set -euo pipefail

TZ_NAME="${LBG_PROXMOX_TIMEZONE:-Europe/Paris}"
SSH_USER="${LBG_PROXMOX_SSH_USER:-root}"
DRY_RUN="${LBG_PROXMOX_TZ_DRY_RUN:-0}"

if [[ -n "${LBG_PROXMOX_SSH_HOSTS:-}" ]]; then
  IFS=',' read -r -a HOSTS <<<"${LBG_PROXMOX_SSH_HOSTS}"
elif [[ -n "${LBG_PROXMOX_HOSTS:-}" ]]; then
  IFS=',' read -r -a HOSTS <<<"${LBG_PROXMOX_HOSTS}"
elif [[ -n "${LBG_PROXMOX_HOST:-}" ]]; then
  HOSTS=("${LBG_PROXMOX_HOST}")
else
  HOSTS=(192.168.0.201)
fi

apply_host() {
  local host="$1"
  echo "=== Proxmox ${SSH_USER}@${host} ==="
  if [[ "${DRY_RUN}" == "1" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=8 "${SSH_USER}@${host}" \
      "timedatectl status; echo '--- dry-run : timedatectl set-timezone ${TZ_NAME}'"
    return 0
  fi
  ssh -o BatchMode=yes -o ConnectTimeout=8 "${SSH_USER}@${host}" \
    "timedatectl set-timezone '${TZ_NAME}' && timedatectl status && pveversion | head -1"
}

for host in "${HOSTS[@]}"; do
  host="${host#https://}"
  host="${host#http://}"
  host="${host%%:*}"
  apply_host "${host}"
done

echo "=== Proxmox timezone OK (${TZ_NAME}) — les VM en cours ne sont pas redémarrées ==="
