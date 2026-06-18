#!/usr/bin/env bash
# Bascule VM 246 : core3-second (galaxy 4) → PreCU stock (galaxy 2).
# 245 reste Prime seul ; DB MariaDB sur 245.
#
# Usage :
#   bash infra/scripts/migrate_core3_second_to_precu_246_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_HOST="${LBG_SOURCE_MMO_HOST:-192.168.0.245}"
DB_HOST="${LBG_CORE3_DB_HOST:-192.168.0.245}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_VM_USER:-lbg}"
TRE_PATH="/opt/lbg-new-mmo/tre"
STOCK_ROOT="/opt/lbg-new-mmo/MMOCoreORB"

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_precu246_%r@%h:%p")
if [[ -n "${LBG_SSH_IDENTITY:-}" ]]; then
  SSH_OPTS+=(-i "${LBG_SSH_IDENTITY}")
fi

echo "=== Migration ${PRECU_HOST} : Second → PreCU (source stock ${SRC_HOST}) ==="

echo "=== Arrêt core3-second + libération disque sur ${PRECU_HOST} ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "sudo systemctl stop lbg-core3-second.service 2>/dev/null || true; sudo systemctl disable lbg-core3-second.service 2>/dev/null || true; pkill -x core3-second 2>/dev/null || true; sleep 2; sudo rm -rf /opt/lbg-new-mmo-clean /opt/lbg-new-mmo/MMOCoreORB /home/sdesharches/lbg-second-prep 2>/dev/null || true; df -h / | tail -1; pgrep -x core3-second && echo WARN_second_still_running || echo second_stopped"

echo "=== Sync stock PreCU ${SRC_HOST} → ${PRECU_HOST} ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${SRC_HOST}" "test -x ${STOCK_ROOT}/bin/core3-swgemu" || {
  echo "ERROR: ${STOCK_ROOT}/bin/core3-swgemu absent sur ${SRC_HOST}" >&2
  exit 1
}
mkdir -p /tmp/lbg-precu-stage
rsync -a -e "ssh ${SSH_OPTS[*]}" \
  --exclude 'bin/log/' \
  --exclude 'build/' \
  "${VM_USER}@${SRC_HOST}:${STOCK_ROOT}/" \
  "/tmp/lbg-precu-stage/MMOCoreORB/"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "sudo mkdir -p /opt/lbg-new-mmo && sudo chown -R ${VM_USER}:${VM_USER} /opt/lbg-new-mmo"
rsync -a -e "ssh ${SSH_OPTS[*]}" \
  "/tmp/lbg-precu-stage/MMOCoreORB/" \
  "${VM_USER}@${PRECU_HOST}:${STOCK_ROOT}/"

echo "=== config-local PreCU (DB distante ${DB_HOST}) ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "bash -s" <<EOF
set -euo pipefail
CONF="${STOCK_ROOT}/bin/conf/config-local.lua"
DBPASS="123456"
if [[ -f "${STOCK_ROOT}/bin/conf/config-local.lua" ]]; then
  DBPASS=\$(grep -E '^Core3\\.DBPass' "${STOCK_ROOT}/bin/conf/config-local.lua" 2>/dev/null | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1 || true)
fi
DBPASS="\${DBPASS:-123456}"
cat > "\${CONF}" <<LUA
-- PreCU VM ${PRECU_HOST} — généré migrate_core3_second_to_precu_246_vm.sh
Core3.TrePath = "${TRE_PATH}"
Core3.DBHost = "${DB_HOST}"
Core3.DBPort = 3306
Core3.DBName = "swgemu"
Core3.DBUser = "swgemu"
Core3.DBPass = "\${DBPASS}"
Core3.MantisHost = "${DB_HOST}"
Core3.MantisPort = 3306
Core3.MantisName = "swgemu"
Core3.MantisUser = "swgemu"
Core3.MantisPass = "\${DBPASS}"
LUA
chmod +x "${STOCK_ROOT}/bin/core3-swgemu"
mkdir -p "${STOCK_ROOT}/bin/log"
touch "${STOCK_ROOT}/bin/log/core3.log"
EOF

scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-precu.service" \
  "${VM_USER}@${PRECU_HOST}:/tmp/lbg-core3-precu.service"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "sudo cp /tmp/lbg-core3-precu.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable lbg-core3-precu.service"

echo "=== SQL galaxy 2 → ${PRECU_HOST} (sur DB ${DB_HOST}) ==="
scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/snippets/core3-galaxy-precu-lan246.sql" \
  "${VM_USER}@${SRC_HOST}:/tmp/core3-galaxy-precu-lan246.sql"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${SRC_HOST}" "sudo mysql swgemu < /tmp/core3-galaxy-precu-lan246.sql"

echo "=== Nettoyage clean/second sur ${PRECU_HOST} (optionnel) ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "sudo systemctl disable lbg-core3-second.service 2>/dev/null || true; rm -rf /home/sdesharches/lbg-second-prep 2>/dev/null || true; sudo rm -rf /opt/lbg-new-mmo-clean 2>/dev/null || true"

echo "=== Démarrage lbg-core3-precu ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "sudo systemctl restart lbg-core3-precu.service; sleep 5; systemctl is-active lbg-core3-precu.service; pgrep -a core3-swgemu || true"

echo ""
echo "OK — PreCU sur ${PRECU_HOST}"
echo "  Client : IP ${PRECU_HOST}, login UDP 44453, galaxie « LBG SWGEMU PreCu » (id 2)"
echo "  Log : ssh ${VM_USER}@${PRECU_HOST} 'tail -f /tmp/core3-swgemu.log'"
echo "  Prime reste sur ${SRC_HOST} (galaxy 3)"
