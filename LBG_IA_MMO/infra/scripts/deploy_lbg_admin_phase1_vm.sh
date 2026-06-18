#!/usr/bin/env bash
# Phase 1 ADR 0006 : niveaux LBG Lua + compat C++ (rebuild) + migration SQL + UI admin
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LBG_MMO="${LBG_MMO_ROOT:-$HOME/projects/new_mmo/lbg-mmo}"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CLEAN_SCRIPTS="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/scripts"
AG_ROOT="/opt/lbg-antigravity/lbg-mmo"

echo "=== 1) Sync sources lbg-mmo → VM Antigravity ==="
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${AG_ROOT}"
rsync -az --delete \
  --exclude '/build/' \
  --exclude '/.git/' \
  "${LBG_MMO}/" "${VM_USER}@${VM_HOST}:${AG_ROOT}/"

echo "=== 2) Scripts staff LBG → runtime Clean ==="
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${CLEAN_SCRIPTS}/staff/levels"
rsync -az \
  "${LBG_MMO}/Core3/MMOCoreORB/bin/scripts/staff/levels/" \
  "${VM_USER}@${VM_HOST}:${CLEAN_SCRIPTS}/staff/levels/"
rsync -az \
  "${LBG_MMO}/Core3/MMOCoreORB/bin/scripts/managers/player_creation_manager.lua" \
  "${VM_USER}@${VM_HOST}:${CLEAN_SCRIPTS}/managers/player_creation_manager.lua"

echo "=== 3) Migration SQL comptes (Teome 15→4, etc.) ==="
ssh "${VM_USER}@${VM_HOST}" "mysql -u swgemu -p123456 swgemu" < "${ROOT}/infra/snippets/core3-admin-level-migrate-lbg.sql"

echo "=== 4) Rebuild core3 (compat AdminLevelCompat) ==="
if [[ -x "${ROOT}/infra/scripts/build_core3_antigravity_vm.sh" ]]; then
  bash "${ROOT}/infra/scripts/build_core3_antigravity_vm.sh"
  bash "${ROOT}/infra/scripts/install_core3_clean_after_vm_build.sh" || true
else
  echo "WARN: build_core3_antigravity_vm.sh absent — rebuild manuel requis"
fi

echo "=== 5) Redémarrage core3-clean (charge nouveaux levels Lua) ==="
ssh "${VM_USER}@${VM_HOST}" 'pkill -x core3-clean 2>/dev/null || true; sleep 3
  cd /opt/lbg-new-mmo-clean/MMOCoreORB/bin
  nohup ./core3-clean > /tmp/core3-clean.log 2>&1 &
  sleep 2
  pgrep -x core3-clean && grep -E "READY|ERROR" /tmp/core3-clean.log | tail -5'

echo "=== 6) UI web comptes ==="
bash "${ROOT}/infra/scripts/start_core3_account_admin_vm.sh"

echo "Phase 1 déployée. Vérifier Teome admin_level=4 et http://${VM_HOST}:8792/"
