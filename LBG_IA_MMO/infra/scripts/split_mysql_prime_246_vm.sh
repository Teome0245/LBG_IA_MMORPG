#!/usr/bin/env bash
# MariaDB locale sur VM 246 — Prime autonome (plus de dépendance MySQL vers 245).
#
# Conserve en commun : launcher + UI comptes http://192.168.0.245:8792/ (PreCU / ops).
# Clients distincts : PreCU → 245:44453 (galaxie 2), Prime → 246:44553 (galaxie 3).
#
# Usage :
#   bash infra/scripts/split_mysql_prime_246_vm.sh --dry-run
#   bash infra/scripts/split_mysql_prime_246_vm.sh
#   bash infra/scripts/split_mysql_prime_246_vm.sh --skip-precu-cleanup
#   bash infra/scripts/split_mysql_prime_246_vm.sh --verify-no-245
#
# Variables :
#   LBG_PRIME_VM_HOST=192.168.0.246
#   LBG_PRECU_VM_HOST=192.168.0.245
#   LBG_CORE3_DB_USER=swgemu
#   LBG_CORE3_DB_PASS=123456
#   LBG_CORE3_DB_NAME=swgemu

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_VM_USER:-lbg}"
DB_USER="${LBG_CORE3_DB_USER:-swgemu}"
DB_PASS="${LBG_CORE3_DB_PASS:-123456}"
DB_NAME="${LBG_CORE3_DB_NAME:-swgemu}"
CLEAN_ROOT="/opt/lbg-new-mmo-clean/MMOCoreORB"
TRE_PATH="/opt/lbg-new-mmo/tre"
DUMP_LOCAL="/tmp/lbg-swgemu-prime-split-$$.sql"

DRY_RUN=0
SKIP_PRECU_CLEANUP=0
VERIFY_NO_245=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --skip-precu-cleanup) SKIP_PRECU_CLEANUP=1 ;;
    --verify-no-245) VERIFY_NO_245=1 ;;
  esac
done

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=10m -o "ControlPath=/tmp/lbg_mysql_split_%r@%h:%p")

_run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

_cleanup_dump() {
  rm -f "${DUMP_LOCAL}"
}
trap _cleanup_dump EXIT

echo "=== Split MySQL Prime : DB locale sur ${PRIME_HOST} | source ${PRECU_HOST} ==="

echo "=== 0) Prérequis réseau ==="
for host in "${PRIME_HOST}" "${PRECU_HOST}"; do
  if ! ping -c 1 -W 3 "${host}" >/dev/null 2>&1; then
    echo "ERROR: ${host} injoignable" >&2
    exit 1
  fi
done

echo "=== 1) Arrêt Prime sur ${PRIME_HOST} ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" \
  "sudo systemctl stop lbg-core3-prime.service 2>/dev/null || true; sleep 2"

echo "=== 2) MariaDB sur ${PRIME_HOST} ==="
_run scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/snippets/core3-mysql-prime-246-post-import.sql" \
  "${ROOT_DIR}/infra/snippets/core3-galaxy-prime-lan246.sql" \
  "${VM_USER}@${PRIME_HOST}:/tmp/"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
if ! command -v mysqld >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq mariadb-server mariadb-client
fi
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
"
EOF

echo "=== 3) Dump ${DB_NAME} depuis ${PRECU_HOST} ==="
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[dry-run] mysqldump ${PRECU_HOST}:${DB_NAME} → ${DUMP_LOCAL}"
else
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" \
    "mysqldump -h127.0.0.1 -u${DB_USER} -p${DB_PASS} --single-transaction --routines --triggers ${DB_NAME}" \
    > "${DUMP_LOCAL}"
  bytes=$(wc -c < "${DUMP_LOCAL}" | tr -d ' ')
  echo "Dump : ${bytes} octets → ${DUMP_LOCAL}"
  if [[ "${bytes}" -lt 1000 ]]; then
    echo "ERROR: dump trop petit" >&2
    exit 1
  fi
fi

echo "=== 4) Import + nettoyage Prime sur ${PRIME_HOST} ==="
if [[ "${DRY_RUN}" != "1" ]]; then
  scp -q "${SSH_OPTS[@]}" "${DUMP_LOCAL}" "${VM_USER}@${PRIME_HOST}:/tmp/lbg-swgemu-import.sql"
fi
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
mysql -h127.0.0.1 -u${DB_USER} -p${DB_PASS} -e "DROP DATABASE IF EXISTS ${DB_NAME}; CREATE DATABASE ${DB_NAME};"
mysql -h127.0.0.1 -u${DB_USER} -p${DB_PASS} ${DB_NAME} < /tmp/lbg-swgemu-import.sql
sudo mysql ${DB_NAME} < /tmp/core3-mysql-prime-246-post-import.sql
sudo mysql ${DB_NAME} < /tmp/core3-galaxy-prime-lan246.sql
rm -f /tmp/lbg-swgemu-import.sql
EOF

echo "=== 5) config-local.lua → DB locale ${PRIME_HOST} ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
CONF="${CLEAN_ROOT}/bin/conf/config-local.lua"
DBPASS="${DB_PASS}"
if [[ -f "\${CONF}" ]]; then
  old=\$(grep -E '^Core3\\.DBPass' "\${CONF}" 2>/dev/null | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1 || true)
  [[ -n "\${old}" ]] && DBPASS="\${old}"
fi
mkdir -p "${CLEAN_ROOT}/bin/log" "${CLEAN_ROOT}/bin/databases"
cat > "\${CONF}" <<LUA
-- Prime VM ${PRIME_HOST} — split_mysql_prime_246_vm.sh (MariaDB locale)
Core3.TrePath = "${TRE_PATH}"
Core3.DBHost = "127.0.0.1"
Core3.DBPort = 3306
Core3.DBName = "${DB_NAME}"
Core3.DBUser = "${DB_USER}"
Core3.DBPass = "\${DBPASS}"
Core3.MantisHost = "127.0.0.1"
Core3.MantisPort = 3306
Core3.MantisName = "${DB_NAME}"
Core3.MantisUser = "${DB_USER}"
Core3.MantisPass = "\${DBPASS}"
Core3.LoginPort = 44553
Core3.PingPort = 44562
Core3.ORBPort = 44519
Core3.StatusPort = 44555
Core3.WebPorts = 44560
Core3.ZoneGalaxyID = 3
LUA
EOF

if [[ "${SKIP_PRECU_CLEANUP}" == "0" ]]; then
  echo "=== 6) Retrait galaxie 3 sur ${PRECU_HOST} (PreCU seul) ==="
  _run scp -q "${SSH_OPTS[@]}" \
    "${ROOT_DIR}/infra/snippets/core3-mysql-precu-245-remove-prime.sql" \
    "${VM_USER}@${PRECU_HOST}:/tmp/"
  _run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" \
    "sudo mysql ${DB_NAME} < /tmp/core3-mysql-precu-245-remove-prime.sql"
else
  echo "=== 6) Nettoyage PreCU ignoré (--skip-precu-cleanup) ==="
fi

echo "=== 7) Redémarrage Prime ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" \
  "sudo systemctl restart lbg-core3-prime.service"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[dry-run] fin — pas de vérif runtime"
  exit 0
fi

echo "=== 8) Attente boot Prime (~90 s) ==="
for i in $(seq 1 18); do
  sleep 5
  if ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" \
    "systemctl is-active lbg-core3-prime.service >/dev/null && ss -ulnp 2>/dev/null | grep -q ':44553 '" 2>/dev/null; then
    echo "Prime READY (tentative ${i})"
    break
  fi
  echo "  … ${i}/18"
done

echo "=== 9) Vérifications ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<'EOF'
set -euo pipefail
systemctl is-active lbg-core3-prime.service
ss -ulnp | grep -E ':44553|:44562|:44563' || true
mysql -h127.0.0.1 -uswgemu -p123456 swgemu -N -e \
  "SELECT CONCAT('galaxy=',galaxy_id,' ',name,' ',address) FROM galaxy; SELECT CONCAT('chars_g3=',COUNT(*)) FROM characters WHERE galaxy_id=3;"
grep -E '^Core3\.DBHost' /opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua
EOF

if [[ "${VERIFY_NO_245}" == "1" ]]; then
  echo "=== 10) Test indépendance (blocage MySQL → 245, 30 s) ==="
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo iptables -C OUTPUT -d ${PRECU_HOST} -p tcp --dport 3306 -j DROP 2>/dev/null \
  || sudo iptables -I OUTPUT -d ${PRECU_HOST} -p tcp --dport 3306 -j DROP
sleep 5
systemctl is-active lbg-core3-prime.service
mysql -h127.0.0.1 -u${DB_USER} -p${DB_PASS} -e 'SELECT 1' >/dev/null
sudo iptables -D OUTPUT -d ${PRECU_HOST} -p tcp --dport 3306 -j DROP
echo "OK — Prime reste actif sans MySQL ${PRECU_HOST}"
EOF
fi

echo ""
echo "=== Terminé ==="
echo "  Prime  : ${PRIME_HOST} — MariaDB locale, login UDP 44553, galaxie 3 seule"
echo "  PreCU  : ${PRECU_HOST} — MariaDB locale, galaxie 2 (Prime retirée si cleanup)"
echo "  UI ops : http://${PRECU_HOST}:8792/ (comptes PreCU ; Prime = DB séparée sur 246)"
echo ""
echo "  OID bots : LBG_CORE3_DB_HOST=${PRIME_HOST} bash infra/scripts/sync_ia_player_oid_vm.sh lia"
echo "  IA       : LBG_NEW_MMO_VM_HOST=${PRIME_HOST} bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
