#!/usr/bin/env bash
# Prépare la VM second Core3 : IP 192.168.0.246 + binaire core3-second (galaxy 4, ports 4465x).
# DB MariaDB partagée sur 245.
#
# Prérequis : SSH lbg@ cible (130 avant migration, puis 246).
# Si seul sdesharches@ est accessible, le script tente bootstrap_lbg_vm_user.sh
# (mot de passe sudo : LBG_VM_SUDO_PASSWORD ou invite interactive).
#
# Usage :
#   bash infra/scripts/setup_core3_second_host_246_vm.sh
#   LBG_SECOND_VM_HOST=192.168.0.130 bash infra/scripts/setup_core3_second_host_246_vm.sh
#   LBG_SKIP_IP_MIGRATION=1 LBG_SECOND_VM_HOST=192.168.0.246 bash infra/scripts/setup_core3_second_host_246_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_HOST="${LBG_SOURCE_MMO_HOST:-192.168.0.245}"
DB_HOST="${LBG_CORE3_DB_HOST:-192.168.0.245}"
VM_USER="${LBG_VM_USER:-lbg}"
BOOTSTRAP_USER="${LBG_BOOTSTRAP_USER:-sdesharches}"
START_HOST="${LBG_SECOND_VM_HOST:-192.168.0.130}"
TARGET_IP="${LBG_SECOND_VM_IP:-192.168.0.246}"
GATEWAY="${LBG_LAN_GATEWAY:-192.168.0.254}"
SKIP_IP="${LBG_SKIP_IP_MIGRATION:-0}"
SKIP_RSYNC="${LBG_SKIP_RSYNC:-0}"
TRE_PATH="/opt/lbg-new-mmo/tre"
CLEAN_ROOT="/opt/lbg-new-mmo-clean/MMOCoreORB"
STOCK_ROOT="/opt/lbg-new-mmo/MMOCoreORB"
RSYNC_EXCLUDES=(
  --exclude 'build/'
  --exclude 'bin/databases/'
  --exclude 'bin/databases.bak*/'
  --exclude 'bin/log/'
  --exclude 'bin/*.bak*'
  --exclude 'bin/core3-clean.bad'
  --exclude 'bin/core3_new'
  --exclude 'bin/hcore3'
  --exclude 'bin/vcore3*'
)

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_second_core3_%r@%h:%p")
if [[ -n "${LBG_SSH_IDENTITY:-}" ]]; then
  SSH_OPTS+=(-i "${LBG_SSH_IDENTITY}")
fi

ssh_ok() {
  local host="$1"
  local user="${2:-${VM_USER}}"
  ssh "${SSH_OPTS[@]}" -o BatchMode=yes -o ConnectTimeout=8 "${user}@${host}" "echo ok" >/dev/null 2>&1
}

echo "=== Core3 Second host → IP ${TARGET_IP} (start SSH: ${START_HOST}, source: ${SRC_HOST}) ==="

if ! ssh_ok "${START_HOST}"; then
  if ssh_ok "${START_HOST}" "${BOOTSTRAP_USER}"; then
    echo "=== Bootstrap compte ${VM_USER} via ${BOOTSTRAP_USER}@${START_HOST} ==="
    LBG_VM_HOST="${START_HOST}" \
      LBG_BOOTSTRAP_USER="${BOOTSTRAP_USER}" \
      LBG_VM_USER="${VM_USER}" \
      LBG_VM_SUDO_PASSWORD="${LBG_VM_SUDO_PASSWORD:-}" \
      bash "${ROOT_DIR}/infra/scripts/bootstrap_lbg_vm_user.sh"
  else
    echo "ERROR: SSH BatchMode échoue vers ${VM_USER}@${START_HOST} et ${BOOTSTRAP_USER}@${START_HOST}" >&2
    echo "Ajoutez la clé publique WSL sur la VM, ou lancez :" >&2
    echo "  LBG_VM_HOST=${START_HOST} LBG_BOOTSTRAP_USER=${BOOTSTRAP_USER} bash infra/scripts/bootstrap_lbg_vm_user.sh" >&2
    exit 1
  fi
fi

if [[ "${SKIP_IP}" != "1" && "${START_HOST}" != "${TARGET_IP}" ]]; then
  echo "=== Migration IP ${START_HOST} → ${TARGET_IP} ==="
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${START_HOST}" "bash -s" <<EOF
set -euo pipefail
TARGET_IP="${TARGET_IP}"
GATEWAY="${GATEWAY}"
IFACE=\$(ip route show default 2>/dev/null | awk '{print \$5}' | head -1)
[[ -n "\${IFACE}" ]] || IFACE=\$(ip -o -4 addr show | awk '!/127.0.0.1/ {print \$2; exit}')
echo "Interface: \${IFACE}"
sudo mkdir -p /etc/netplan
sudo tee /etc/netplan/01-lbg-static.yaml >/dev/null <<YAML
network:
  version: 2
  ethernets:
    \${IFACE}:
      dhcp4: false
      addresses: [\${TARGET_IP}/24]
      routes:
        - to: default
          via: \${GATEWAY}
      nameservers:
        addresses: [\${GATEWAY}, 8.8.8.8]
YAML
sudo chmod 600 /etc/netplan/01-lbg-static.yaml
sudo netplan apply
ip -4 -br addr show "\${IFACE}"
EOF
  echo "Attente reconnexion sur ${TARGET_IP}…"
  for i in $(seq 1 30); do
    if ssh_ok "${TARGET_IP}"; then
      break
    fi
    sleep 2
  done
  if ! ssh_ok "${TARGET_IP}"; then
    echo "ERROR: pas de SSH sur ${TARGET_IP} après migration IP" >&2
    exit 1
  fi
  WORK_HOST="${TARGET_IP}"
else
  WORK_HOST="${START_HOST}"
fi

echo "=== MySQL LAN (245) pour le host Second ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${SRC_HOST}" "bash -s" <<EOS
set -euo pipefail
CNF=/etc/mysql/mariadb.conf.d/50-server.cnf
if grep -q '^bind-address' "\$CNF" 2>/dev/null && grep -q '127.0.0.1' "\$CNF"; then
  echo "Ouverture MariaDB LAN (bind 0.0.0.0) pour ${TARGET_IP}…"
  sudo sed -i 's/^bind-address.*/bind-address            = 0.0.0.0/' "\$CNF"
  sudo systemctl restart mariadb || sudo systemctl restart mysql
fi
mysql swgemu -e "CREATE USER IF NOT EXISTS 'swgemu'@'${TARGET_IP}' IDENTIFIED BY '123456'; GRANT ALL ON swgemu.* TO 'swgemu'@'${TARGET_IP}'; FLUSH PRIVILEGES;" 2>/dev/null \\
  || sudo mysql swgemu -e "CREATE USER IF NOT EXISTS 'swgemu'@'${TARGET_IP}' IDENTIFIED BY '123456'; GRANT ALL ON swgemu.* TO 'swgemu'@'${TARGET_IP}'; FLUSH PRIVILEGES;"
EOS

if [[ "${SKIP_RSYNC}" != "1" ]]; then
  echo "=== Sync stack MMO depuis ${SRC_HOST} vers ${WORK_HOST} ==="
  ssh "${SSH_OPTS[@]}" -o BatchMode=yes "${VM_USER}@${SRC_HOST}" "test -d ${CLEAN_ROOT}/bin" || {
    echo "ERROR: ${CLEAN_ROOT}/bin absent sur ${SRC_HOST}" >&2
    exit 1
  }

  # rsync via machine locale (double hop, excludes lourds : logs 74G, DB locale)
  mkdir -p /tmp/lbg-second-stage
  rsync -a -e "ssh ${SSH_OPTS[*]}" \
    "${RSYNC_EXCLUDES[@]}" \
    "${VM_USER}@${SRC_HOST}:${CLEAN_ROOT}/" \
    "/tmp/lbg-second-stage/MMOCoreORB/"

  if ssh "${SSH_OPTS[@]}" -o BatchMode=yes "${VM_USER}@${SRC_HOST}" "test -d ${TRE_PATH}"; then
    rsync -a -e "ssh ${SSH_OPTS[*]}" \
      "${VM_USER}@${SRC_HOST}:${TRE_PATH}/" \
      "/tmp/lbg-second-stage/tre/" || true
  fi

  ssh "${SSH_OPTS[@]}" "${VM_USER}@${WORK_HOST}" "sudo mkdir -p /opt/lbg-new-mmo-clean /opt/lbg-new-mmo && sudo chown -R ${VM_USER}:${VM_USER} /opt/lbg-new-mmo-clean /opt/lbg-new-mmo"
  rsync -a -e "ssh ${SSH_OPTS[*]}" \
    "/tmp/lbg-second-stage/MMOCoreORB/" \
    "${VM_USER}@${WORK_HOST}:/opt/lbg-new-mmo-clean/MMOCoreORB/"
  if [[ -d /tmp/lbg-second-stage/tre ]]; then
    rsync -a -e "ssh ${SSH_OPTS[*]}" \
      "/tmp/lbg-second-stage/tre/" \
      "${VM_USER}@${WORK_HOST}:${TRE_PATH}/"
  fi
else
  echo "=== Sync MMO ignoré (LBG_SKIP_RSYNC=1) ==="
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${WORK_HOST}" "test -x ${CLEAN_ROOT}/bin/core3-clean || test -x ${CLEAN_ROOT}/bin/core3-second" || {
    echo "ERROR: binaire core3 absent sur ${WORK_HOST} (retirer LBG_SKIP_RSYNC ou relancer root)" >&2
    exit 1
  }
fi

scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-second.service" \
  "${VM_USER}@${WORK_HOST}:/tmp/lbg-core3-second.service"

echo "=== Config locale + binaire core3-second sur ${WORK_HOST} ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${WORK_HOST}" "bash -s" <<EOF
set -euo pipefail
CLEAN_BIN="${CLEAN_ROOT}/bin"
STOCK_BIN="${STOCK_ROOT}/bin"
mkdir -p "\${CLEAN_BIN}/databases" "\${CLEAN_BIN}/log" "\${CLEAN_BIN}/conf"
touch "\${CLEAN_BIN}/log/core3.log" "\${CLEAN_BIN}/ia_bridge/pending.jsonl"

if [[ -x "\${CLEAN_BIN}/core3-clean" ]]; then
  cp "\${CLEAN_BIN}/core3-clean" "\${CLEAN_BIN}/core3-second"
elif [[ -x "\${STOCK_BIN}/core3" ]]; then
  cp "\${STOCK_BIN}/core3" "\${CLEAN_BIN}/core3-second"
else
  echo "ERROR: binaire core3 absent" >&2
  exit 1
fi
chmod +x "\${CLEAN_BIN}/core3-second"

DBPASS="123456"
if [[ -f "\${CLEAN_BIN}/conf/config-local.lua" ]]; then
  DBPASS=\$(grep -E '^Core3\\.DBPass' "\${CLEAN_BIN}/conf/config-local.lua" | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1)
fi

cat > "\${CLEAN_BIN}/conf/config-local.lua" <<LUA
-- Instance Core3 Second (galaxy 4) — généré setup_core3_second_host_246_vm.sh
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
Core3.LoginPort = 44653
Core3.PingPort = 44662
Core3.ORBPort = 44619
Core3.StatusPort = 44655
Core3.WebPorts = 44660
Core3.ZoneGalaxyID = 4
LUA

sudo cp /tmp/lbg-core3-second.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-second.service
EOF

echo "=== Galaxie SQL (galaxy_id=4) sur DB ${DB_HOST} ==="
scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/snippets/core3-galaxy-second-lan246.sql" \
  "${VM_USER}@${SRC_HOST}:/tmp/core3-galaxy-second-lan246.sql"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${SRC_HOST}" "bash -s" <<'EOS'
set -euo pipefail
SQL=/tmp/core3-galaxy-second-lan246.sql
if mysql swgemu < "$SQL" 2>/dev/null; then
  :
else
  sudo mysql swgemu < "$SQL"
fi
EOS

echo "=== Démarrage lbg-core3-second ==="
ssh "${SSH_OPTS[@]}" "${VM_USER}@${WORK_HOST}" "sudo systemctl restart lbg-core3-second.service; sleep 3; systemctl is-active lbg-core3-second.service; pgrep -a core3-second || true"

echo ""
echo "OK — Serveur Second sur ${WORK_HOST}"
echo "  Client : IP ${TARGET_IP}, login UDP 44653, galaxie « LBG MMO Serveur Second » (id 4)"
echo "  Log : ssh ${VM_USER}@${WORK_HOST} 'tail -f /tmp/core3-second.log'"
echo "  DB galaxy : ssh ${VM_USER}@${SRC_HOST} \"mysql -N swgemu -e 'SELECT * FROM galaxy WHERE galaxy_id=4'\""
