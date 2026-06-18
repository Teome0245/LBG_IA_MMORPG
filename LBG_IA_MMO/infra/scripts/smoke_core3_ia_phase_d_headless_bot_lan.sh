#!/usr/bin/env bash
# Smoke Phase D — core3client present + login-only + garde snapshot.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke Phase D — headless Lia → ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" 'bash -s' <<'EOF'
set -euo pipefail
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin
test -x "${BIN}/core3client"
test -f "${BIN}/ia_bridge/lia_bot_session.json"
systemctl cat lbg-core3-ia-bot-client.service >/dev/null 2>&1 || true
cd "${BIN}"
export CORE3_CLIENT_USERNAME=Bot_IA
export CORE3_CLIENT_PASSWORD="${CORE3_IA_BOT_PASSWORD:-lbgiabot}"
./core3client --login-only --login-host 127.0.0.1 --login-port 44553 2>&1 | grep -q "Authentication successful"
echo "OK login-only"
EOF

echo "=== Smoke Phase D OK ==="
