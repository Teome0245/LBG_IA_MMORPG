#!/usr/bin/env bash
# Aligne le fuseau affiché sur Europe/Paris (CEST/CET) sans toucher l'horloge système.
# NTP reste actif : seul le timezone local change (sûr pendant un build cmake en cours).
#
# Usage local sur une VM :
#   sudo bash infra/scripts/set_vm_timezone_europe_paris.sh
#
# Usage LAN (défaut : 110, 140, 245, 246) :
#   bash infra/scripts/set_vm_timezone_europe_paris.sh
#
# Une seule VM :
#   LBG_VM_HOSTS=192.168.0.246 bash infra/scripts/set_vm_timezone_europe_paris.sh

set -euo pipefail

TZ_NAME="${LBG_VM_TIMEZONE:-Europe/Paris}"
VM_USER="${LBG_VM_USER:-lbg}"

apply_local() {
  if ! command -v timedatectl >/dev/null 2>&1; then
    echo "ERROR: timedatectl absent sur cette machine" >&2
    exit 1
  fi
  sudo timedatectl set-timezone "${TZ_NAME}"
  timedatectl status
}

apply_remote() {
  local host="$1"
  echo "=== ${host} ==="
  ssh -o BatchMode=yes -o ConnectTimeout=6 "${VM_USER}@${host}" \
    "sudo -n timedatectl set-timezone '${TZ_NAME}' && timedatectl status"
}

if [[ "${1:-}" == "--local" ]]; then
  apply_local
  exit 0
fi

if [[ -n "${LBG_VM_HOST:-}" ]]; then
  HOSTS=("${LBG_VM_HOST}")
elif [[ -n "${LBG_VM_HOSTS:-}" ]]; then
  IFS=',' read -r -a HOSTS <<<"${LBG_VM_HOSTS}"
else
  HOSTS=(192.168.0.110 192.168.0.140 192.168.0.245 192.168.0.246)
fi

for host in "${HOSTS[@]}"; do
  apply_remote "${host}"
done
