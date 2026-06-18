#!/usr/bin/env bash
# Récupère les sources Core3 depuis une VM vers le dépôt local new_mmo (secours).
# Usage :
#   bash infra/scripts/pull_core3_from_vm.sh precu    # 245 → lbg-mmo/Core3/MMOCoreORB
#   bash infra/scripts/pull_core3_from_vm.sh prime    # 246 → server-core3 + MMOEngine
#   bash infra/scripts/pull_core3_from_vm.sh both

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.245}"
PRIME_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"

if [[ -n "${LBG_NEW_MMO_REPO:-}" ]]; then
  NEW_MMO_REPO="$(cd "${LBG_NEW_MMO_REPO}" && pwd)"
else
  for _cand in "${ROOT}/../../new_mmo" "${ROOT}/../new_mmo"; do
    if [[ -d "${_cand}/lbg-mmo" ]]; then
      NEW_MMO_REPO="$(cd "${_cand}" && pwd)"
      break
    fi
  done
fi

if [[ -z "${NEW_MMO_REPO:-}" ]]; then
  echo "ERROR: dépôt new_mmo introuvable (définir LBG_NEW_MMO_REPO)" >&2
  exit 1
fi

TARGET="${1:-both}"
RSYNC_EX=(
  --archive
  --partial
  --human-readable
  --exclude 'build/'
  --exclude 'bin/'
  --exclude 'databases/'
  --exclude 'log/'
  --exclude '*.tre'
  --exclude 'config-local.lua'
  --exclude '.env*'
)

pull_precu() {
  local remote="/opt/lbg-new-mmo/MMOCoreORB"
  local local_dir="${NEW_MMO_REPO}/lbg-mmo/Core3/MMOCoreORB"
  echo "=== PreCU : ${VM_USER}@${PRECU_HOST}:${remote} → ${local_dir}"
  mkdir -p "${local_dir}"
  rsync "${RSYNC_EX[@]}" -e ssh \
    "${VM_USER}@${PRECU_HOST}:${remote}/" \
    "${local_dir}/"
}

pull_prime() {
  local remote="/opt/lbg-antigravity/lbg-mmo"
  local local_base="${NEW_MMO_REPO}/lbg-mmo"
  echo "=== Prime : ${VM_USER}@${PRIME_HOST}:${remote} → ${local_base}"
  for sub in server-core3 MMOEngine; do
    mkdir -p "${local_base}/${sub}"
    rsync "${RSYNC_EX[@]}" -e ssh \
      "${VM_USER}@${PRIME_HOST}:${remote}/${sub}/" \
      "${local_base}/${sub}/"
  done
  # Screenplays custom déployés (runtime) — aligner si édités sur VM
  local lua_remote="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/scripts/custom_scripts/screenplays"
  local lua_local="${ROOT}/content/core3/lua"
  if ssh -o BatchMode=yes "${VM_USER}@${PRIME_HOST}" "test -d ${lua_remote}"; then
    echo "=== Lua custom VM → LBG_IA_MMO/content/core3/lua"
    rsync "${RSYNC_EX[@]}" -e ssh \
      "${VM_USER}@${PRIME_HOST}:${lua_remote}/" \
      "${lua_local}/"
  fi
}

case "${TARGET}" in
  precu) pull_precu ;;
  prime) pull_prime ;;
  both) pull_precu; pull_prime ;;
  *)
    echo "Usage: $0 {precu|prime|both}" >&2
    exit 2
    ;;
esac

echo "OK — vérifier avec git -C ${NEW_MMO_REPO} status"
