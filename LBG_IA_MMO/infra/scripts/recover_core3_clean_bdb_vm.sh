#!/usr/bin/env bash
# Recovery Berkeley DB pour Serveur Prime (core3-clean, VM 245).
# Usage : bash infra/scripts/recover_core3_clean_bdb_vm.sh [--no-restart]
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
NO_RESTART=0
for arg in "$@"; do
  case "$arg" in
    --no-restart) NO_RESTART=1 ;;
  esac
done

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
DB="\${BIN}/databases"
ts=\$(date +%Y%m%d_%H%M%S)

echo "=== Stop core3-clean ==="
if systemctl is-active lbg-core3-prime.service &>/dev/null; then
  sudo systemctl stop lbg-core3-prime.service
fi
pkill -x core3-clean 2>/dev/null || true
for _ in \$(seq 1 30); do
  pgrep -x core3-clean >/dev/null || break
  sleep 1
done
if pgrep -x core3-clean >/dev/null; then
  echo "ERROR: core3-clean encore actif — recovery annulé" >&2
  exit 1
fi

echo "=== Backup \${DB} -> databases.bak.\${ts} ==="
cp -a "\${DB}" "\${BIN}/databases.bak.\${ts}"

if ! command -v db_recover >/dev/null 2>&1; then
  echo "ERROR: db_recover introuvable (Berkeley DB 5.3)" >&2
  exit 1
fi

echo "=== db_recover ==="
cd "\${DB}"
db_recover -h . -v

echo "=== db_verify (échantillon) ==="
db_verify -V 2>&1 | tail -20

if [[ "${NO_RESTART}" == "1" ]]; then
  echo "=== Terminé (--no-restart) ==="
  exit 0
fi

echo "=== Start lbg-core3-prime ==="
if systemctl is-enabled lbg-core3-prime.service &>/dev/null; then
  sudo systemctl start lbg-core3-prime.service
else
  cd "\${BIN}"
  nohup ./core3-clean >>/tmp/core3-clean.log 2>&1 &
fi
sleep 2
pgrep -a core3-clean || { echo "WARN: core3-clean absent" >&2; exit 1; }
echo "Suivi : tail -f /tmp/core3-clean.log  (attendre READY)"
EOF
