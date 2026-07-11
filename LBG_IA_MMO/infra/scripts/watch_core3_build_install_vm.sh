#!/usr/bin/env bash
# Attend la fin du build Antigravity sur 246 puis installe core3-clean + smoke ZB-1.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
LOG="/tmp/core3-antigravity-build.log"
POLL_S="${POLL_S:-30}"
MAX_WAIT_S="${MAX_WAIT_S:-7200}"

echo "=== Watch build → install (${VM_USER}@${VM_HOST}) ==="
deadline=$((SECONDS + MAX_WAIT_S))
while (( SECONDS < deadline )); do
  if ssh -o BatchMode=yes "${VM_USER}@${VM_HOST}" "grep -q 'Built target core3' '${LOG}' 2>/dev/null"; then
    echo "Build terminé — installation core3-clean…"
    LBG_NEW_MMO_VM_HOST="${VM_HOST}" bash "${ROOT_DIR}/infra/scripts/install_core3_clean_after_vm_build.sh"
    sleep 15
    ssh "${VM_USER}@${VM_HOST}" "ls -la /opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/zone_bridge_live.json 2>/dev/null || echo 'feed pas encore créé (Prime boot?)'"
    exit 0
  fi
  if ! ssh -o BatchMode=yes "${VM_USER}@${VM_HOST}" "pgrep -f 'cmake --build.*core3' >/dev/null"; then
    if ssh -o BatchMode=yes "${VM_USER}@${VM_HOST}" "grep -qi 'error:' '${LOG}' 2>/dev/null"; then
      echo "Build arrêté avec erreurs — voir ${LOG}" >&2
      ssh "${VM_USER}@${VM_HOST}" "tail -30 '${LOG}'" >&2 || true
      exit 2
    fi
    echo "Build process absent — attente log Built target…"
  fi
  pct=$(ssh -o BatchMode=yes "${VM_USER}@${VM_HOST}" "grep -E '\\[[0-9]+%\\]' '${LOG}' 2>/dev/null | tail -1" || true)
  echo "$(date -Is) ${pct:-…}"
  sleep "${POLL_S}"
done
echo "Timeout ${MAX_WAIT_S}s" >&2
exit 1
