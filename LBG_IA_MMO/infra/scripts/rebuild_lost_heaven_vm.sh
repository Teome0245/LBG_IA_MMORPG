#!/usr/bin/env bash
# Recompile Core3 (patch Z moyen + Lua Lost Heaven v4), installe core3-clean, redéploie le pont IA.
#
# Usage :
#   bash infra/scripts/rebuild_lost_heaven_vm.sh
#   bash infra/scripts/rebuild_lost_heaven_vm.sh --no-wait   # lance le build et sort (suivre le log à la main)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BUILD_LOG="/tmp/core3-antigravity-build.log"
NO_WAIT=0

for arg in "$@"; do
  case "$arg" in
    --no-wait) NO_WAIT=1 ;;
  esac
done

echo "=== 1/4 rsync lbg-mmo (server-core3 + patch StructureManager) ==="
bash "${ROOT_DIR}/infra/scripts/rsync_lbg_mmo_antigravity_vm.sh"

echo "=== 2/4 build Antigravity sur ${VM_HOST} ==="
bash "${ROOT_DIR}/infra/scripts/build_core3_antigravity_vm.sh"

if [[ "${NO_WAIT}" == "1" ]]; then
  echo "Build en arrière-plan. Puis :"
  echo "  ssh ${VM_USER}@${VM_HOST} 'tail -f ${BUILD_LOG}'"
  echo "  bash ${ROOT_DIR}/infra/scripts/install_core3_clean_after_vm_build.sh"
  echo "  bash ${ROOT_DIR}/infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
  echo "  # IG Tatooine : touch ia_bridge/lost_heaven_force_rebuild puis lbg_we hub clean / hub build"
  exit 0
fi

echo "=== Attente fin de build (max ~90 min) ==="
for i in $(seq 1 540); do
  if ssh "${VM_USER}@${VM_HOST}" "grep -q '\\[100%\\] Built target core3' '${BUILD_LOG}' 2>/dev/null"; then
    echo "Build terminé (${i}×10s)."
    break
  fi
  if ssh "${VM_USER}@${VM_HOST}" "grep -qi 'error:' '${BUILD_LOG}' 2>/dev/null && ! pgrep -f 'cmake --build' >/dev/null 2>&1"; then
    echo "ERROR: échec build — voir ${BUILD_LOG}" >&2
    ssh "${VM_USER}@${VM_HOST}" "tail -40 '${BUILD_LOG}'" || true
    exit 1
  fi
  if [[ "$((i % 18))" -eq 0 ]]; then
    echo "  … en cours (${i}×10s)"
    ssh "${VM_USER}@${VM_HOST}" "tail -3 '${BUILD_LOG}' 2>/dev/null" || true
  fi
  sleep 10
done

if ! ssh "${VM_USER}@${VM_HOST}" "grep -q '\\[100%\\] Built target core3' '${BUILD_LOG}' 2>/dev/null"; then
  echo "WARN: timeout attente build — vérifier manuellement : tail -f ${BUILD_LOG}" >&2
  exit 1
fi

echo "=== 3/4 install core3-clean + restart prime ==="
bash "${ROOT_DIR}/infra/scripts/install_core3_clean_after_vm_build.sh"

echo "=== 4/4 deploy Lua Lost Heaven v4 ==="
bash "${ROOT_DIR}/infra/scripts/deploy_core3_ia_bridge_vm.sh" --restart

ssh "${VM_USER}@${VM_HOST}" "touch /opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/lost_heaven_force_rebuild 2>/dev/null || true"

echo ""
echo "=== OK — en jeu (Tatooine, admin) ==="
echo "  /lbg_we hub clean"
echo "  /lbg_we hub build"
echo "Le message système doit afficher Lost Heaven v4 + coordonnées du plateau."
