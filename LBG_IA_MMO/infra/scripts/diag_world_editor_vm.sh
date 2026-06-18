#!/usr/bin/env bash
# Diagnostic World Editor sur VM 245 (à lancer pendant que Teome est connecté).
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

echo "=== World Editor diagnostic ==="
ssh "${VM_USER}@${VM_HOST}" bash -s <<'EOF'
set -euo pipefail
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

echo "-- Service"
systemctl is-active lbg-core3-prime || true

echo "-- Compte SQL Teome"
mysql -uswgemu -p123456 swgemu -N -e \
  "SELECT c.character_oid, a.admin_level FROM characters c JOIN accounts a ON a.account_id=c.account_id WHERE LOWER(c.firstname)='teome';" 2>/dev/null || echo "(mysql KO)"

echo "-- Cache admin compte (ia_bridge)"
cat "${BIN}/ia_bridge/lbg_account_admin.json" 2>/dev/null || echo "(fichier absent — relancer deploy)"

echo "-- Lua déployé (CHAT observer?)"
grep -c 'attachChatObserver\|CHAT\|getEffectiveAdmin' "${BIN}/scripts/custom_scripts/screenplays/lbg_world_editor_screenplay.lua" || true
ls -la "${BIN}/scripts/custom_scripts/screenplays/lbg_world_editor_screenplay.lua"

echo "-- Session / queue"
ls -la "${BIN}/ia_bridge/world_editor_session.json" "${BIN}/ia_bridge/world_editor_cmd.queue" 2>/dev/null || true
cat "${BIN}/ia_bridge/world_editor_session.json" 2>/dev/null || echo "(session vide)"

echo "-- Logs récents"
grep -E 'LbgWorldEditor|WorldEditor|hooks actifs|pollCmdQueue|onSpatialChat' /tmp/core3-clean.log 2>/dev/null | tail -20 || true

echo "-- Test queue session on (Teome EN LIGNE, OID récent si plusieurs persos)"
TEOME_OID="$(mysql -uswgemu -p123456 swgemu -N -e \
  "SELECT c.character_oid FROM characters c WHERE LOWER(c.firstname)='teome' ORDER BY c.creation_date DESC LIMIT 1;" 2>/dev/null || true)"
if [[ -z "${TEOME_OID}" ]]; then
  TEOME_OID="281474993950032"
fi
echo "OID test: ${TEOME_OID}"
echo "${TEOME_OID}|Teome|session on" >> "${BIN}/ia_bridge/world_editor_cmd.queue"
sleep 2
echo "session après test queue:"
cat "${BIN}/ia_bridge/world_editor_session.json" 2>/dev/null || echo "(toujours vide)"
wc -c "${BIN}/ia_bridge/world_editor_cmd.queue" 2>/dev/null || true
grep -E 'pollCmdQueue' /tmp/core3-clean.log 2>/dev/null | tail -5 || true

echo "-- Patch client HTTP"
curl -sf http://127.0.0.1:8080/patches/prime/manifest.json | python3 -c "
import json,sys
m=json.load(sys.stdin)
print('manifest', m.get('version'))
for f in m.get('files',[]):
    if f['name'] in ('patch_lbg_00.tre','swgemu_live.cfg','user.cfg'):
        print(' ', f['name'], f['hash'][:16])
" 2>/dev/null || echo "patch server KO"
EOF

echo ""
echo "Interprétation:"
echo "  - active=1 après test → file/queue OK ; si spatial KO → observers ou texte chat"
echo "  - pollCmdQueue skip (pas Dev+) → regénérer lbg_account_admin.json (deploy)"
echo "  - pollCmdQueue skip (joueur absent) → Teome pas connecté ou mauvais OID"
echo "  - pas de 'hooks actifs pour Teome' → relog après deploy Lua"
