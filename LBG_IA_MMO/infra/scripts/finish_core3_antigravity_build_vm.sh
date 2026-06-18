#!/usr/bin/env bash
# Arrête les builds parallèles, finalise core3 (link + copie bin), installe core3-clean.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SRC="/opt/lbg-antigravity/lbg-mmo"
BUILD="${SRC}/build"
BIN_RUNTIME="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
pkill -9 -f "\${BUILD}" 2>/dev/null || true
pkill -9 -f "idlc.compiler.Compiler" 2>/dev/null || true
sleep 2

mkdir -p "\${SRC}/bin"
LOG=/tmp/core3-antigravity-finish.log
: > "\${LOG}"

echo "=== Link core3 (un seul job) ===" | tee -a "\${LOG}"
cd "\${BUILD}"
if ! cmake --build . -j4 --target core3 >> "\${LOG}" 2>&1; then
  # Si échec uniquement sur la copie POST_BUILD, récupérer le binaire linké
  if [[ -x "\${BUILD}/server-core3/core3" ]]; then
    echo "Link OK, copie POST_BUILD échouée — copie manuelle" | tee -a "\${LOG}"
    cp -a "\${BUILD}/server-core3/core3" "\${SRC}/bin/core3"
  else
    tail -30 "\${LOG}"
    exit 1
  fi
fi

if [[ ! -x "\${SRC}/bin/core3" ]] && [[ -x "\${BUILD}/server-core3/core3" ]]; then
  cp -a "\${BUILD}/server-core3/core3" "\${SRC}/bin/core3"
fi

chmod +x "\${SRC}/bin/core3" "\${BUILD}/server-core3/core3" 2>/dev/null || true
echo "Binaire : \$(ls -la "\${SRC}/bin/core3" "\${BUILD}/server-core3/core3" 2>/dev/null)"
ldd "\${SRC}/bin/core3" >/dev/null

cp -a "\${SRC}/bin/core3" "\${BIN_RUNTIME}/core3-clean"
chmod +x "\${BIN_RUNTIME}/core3-clean"
pkill -x core3-clean 2>/dev/null || true
sleep 1
cd "\${BIN_RUNTIME}"
nohup ./core3-clean > /tmp/core3-clean.log 2>&1 &
echo "core3-clean démarré PID \$! — log /tmp/core3-clean.log"
EOF

echo "=== Terminé ==="
