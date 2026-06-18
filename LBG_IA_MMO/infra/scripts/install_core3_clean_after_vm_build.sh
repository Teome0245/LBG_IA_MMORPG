#!/usr/bin/env bash
# Après compilation sur la VM, installe core3-clean (Antigravity ou MMOCoreORB) et redémarre l'instance.
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
CANDIDATES=(
  "/opt/lbg-antigravity/lbg-mmo/build/server-core3/core3"
  "/opt/lbg-new-mmo-clean/MMOCoreORB/build/src/core3"
  "/opt/lbg-new-mmo-clean/MMOCoreORB/build/bin/core3"
  "${BIN}/core3"
)

stop_clean() {
  pkill -x core3-clean 2>/dev/null || true
  for _ in $(seq 1 30); do
    pgrep -x core3-clean >/dev/null || return 0
    sleep 1
  done
  echo "WARN: core3-clean encore actif, kill -9" >&2
  pkill -9 -x core3-clean 2>/dev/null || true
  sleep 2
}

for c in "${CANDIDATES[@]}"; do
  if [[ -x "$c" ]] && ldd "$c" >/dev/null 2>&1; then
    stop_clean
    tmp="${BIN}/core3-clean.new"
    dest="${BIN}/core3-clean"
    cp -a "$c" "${tmp}"
    chmod +x "${tmp}"
    mv -f "${tmp}" "${dest}"
    echo "Installé : ${dest} ($(stat -c%s "${dest}") bytes) depuis $c"
    if strings "${dest}" | grep -q writeIaBridgePlayerSnapshot; then
      echo "Phase B : writeIaBridgePlayerSnapshot présent"
    else
      echo "WARN: symbole snapshot absent"
    fi
    cd "${BIN}"
    if systemctl is-enabled lbg-core3-prime.service &>/dev/null; then
      sudo systemctl restart lbg-core3-prime.service
      echo "Redémarré via lbg-core3-prime.service — log /tmp/core3-clean.log"
    else
      nohup ./core3-clean >>/tmp/core3-clean.log 2>&1 &
      echo "Démarré PID $! — log /tmp/core3-clean.log"
    fi
    exit 0
  fi
done

echo "ERROR: aucun binaire core3 compatible. Build Antigravity en cours ?" >&2
echo "  tail -f /tmp/core3-antigravity-build.log" >&2
exit 1
EOF
