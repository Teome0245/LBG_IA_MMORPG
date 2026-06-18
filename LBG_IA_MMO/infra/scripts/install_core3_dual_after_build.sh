#!/usr/bin/env bash
# Installe le binaire core3 Antigravity sur core3-clean ET core3-swgemu, redémarre les deux.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SRC="/opt/lbg-antigravity/lbg-mmo/build/server-core3/core3"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
SRC="${SRC}"
STOCK_BIN="/opt/lbg-new-mmo/MMOCoreORB/bin/core3-swgemu"
CLEAN_BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/core3-clean"

if [[ ! -x "\$SRC" ]]; then
  echo "ERROR: binaire absent — lancer build_core3_antigravity_vm.sh d'abord" >&2
  exit 1
fi

for name in core3-clean core3-swgemu; do
  pkill -x "\$name" 2>/dev/null || true
done
sleep 4

cp -a "\$SRC" "\$CLEAN_BIN"
cp -a "\$SRC" "\$STOCK_BIN"
chmod +x "\$CLEAN_BIN" "\$STOCK_BIN"
echo "Installé clean : \$(stat -c%s "\$CLEAN_BIN") bytes"
echo "Installé stock : \$(stat -c%s "\$STOCK_BIN") bytes"

cd /opt/lbg-new-mmo-clean/MMOCoreORB/bin
nohup ./core3-clean > /tmp/core3-clean.log 2>&1 &
if [[ -f /home/lbg/.config/lbg/core3-precu-disabled ]] || [[ "\${CORE3_START_PRECU:-0}" != "1" ]]; then
  pkill -x core3-swgemu 2>/dev/null || true
  echo "PreCu non redémarré (Prime seul — CORE3_START_PRECU=1 pour dual)"
else
  cd /opt/lbg-new-mmo/MMOCoreORB/bin
  nohup ./core3-swgemu > /tmp/core3-swgemu.log 2>&1 &
fi
sleep 2
pgrep -a 'core3-clean|core3-swgemu' || true
EOF
