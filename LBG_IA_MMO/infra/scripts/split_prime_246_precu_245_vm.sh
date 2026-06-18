#!/usr/bin/env bash
# Séparation stricte : VM 246 = Prime seul | VM 245 = PreCU seul (+ MariaDB).
#
# Usage :
#   bash infra/scripts/split_prime_246_precu_245_vm.sh --dry-run
#   bash infra/scripts/split_prime_246_precu_245_vm.sh
#   bash infra/scripts/split_prime_246_precu_245_vm.sh --reboot-246   # reboot 246 avant sync
#
# Variables :
#   LBG_PRIME_VM_HOST=192.168.0.246
#   LBG_PRECU_VM_HOST=192.168.0.245
#   LBG_CORE3_DB_HOST=192.168.0.245

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.245}"
DB_HOST="${LBG_CORE3_DB_HOST:-192.168.0.245}"
VM_USER="${LBG_VM_USER:-lbg}"
TRE_PATH="/opt/lbg-new-mmo/tre"
CLEAN_ROOT="/opt/lbg-new-mmo-clean/MMOCoreORB"
STOCK_ROOT="/opt/lbg-new-mmo/MMOCoreORB"

DRY_RUN=0
REBOOT_246=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --reboot-246) REBOOT_246=1 ;;
  esac
done

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=10m -o "ControlPath=/tmp/lbg_split_%r@%h:%p")

_run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

echo "=== Split Core3 : Prime@${PRIME_HOST} | PreCU@${PRECU_HOST} | DB@${DB_HOST} ==="

if [[ "${REBOOT_246}" == "1" ]]; then
  echo "=== Reboot ${PRIME_HOST} ==="
  _run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "sudo reboot" || true
  echo "Attente SSH ${PRIME_HOST}…"
  for _ in $(seq 1 60); do
    sleep 5
    if ssh "${SSH_OPTS[@]}" -o ConnectTimeout=3 "${VM_USER}@${PRIME_HOST}" "echo up" 2>/dev/null; then
      break
    fi
  done
fi

echo "=== 1) Arrêt services ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" \
  "sudo systemctl stop lbg-core3-prime.service 2>/dev/null || true; sudo systemctl disable lbg-core3-prime.service 2>/dev/null || true; pkill -x core3-clean 2>/dev/null || true"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" \
  "sudo systemctl stop lbg-core3-precu.service 2>/dev/null || true; sudo systemctl disable lbg-core3-precu.service 2>/dev/null || true; pkill -x core3-swgemu 2>/dev/null || true"
sleep 3

echo "=== 2) Troncature logs 245 (bin/log ~74G) ==="
_run bash "${ROOT_DIR}/infra/scripts/truncate_core3_logs_vm.sh" precu 2>/dev/null || true
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "bash -s" <<'EOF'
set -euo pipefail
:> /tmp/core3-clean.log 2>/dev/null || true
find /opt/lbg-new-mmo-clean/MMOCoreORB/bin/log -type f -name '*.log' -exec truncate -s 0 {} + 2>/dev/null || true
find /opt/lbg-new-mmo-clean/MMOCoreORB/bin -maxdepth 1 -name 'core3-clean.bak.*' -delete 2>/dev/null || true
find /opt/lbg-new-mmo-clean/MMOCoreORB/bin -maxdepth 1 -name 'databases.bak.*' -type d -exec rm -rf {} + 2>/dev/null || true
df -h / | tail -1
EOF

echo "=== 3) Sync PreCU → ${PRECU_HOST} (stock local) ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "test -x ${STOCK_ROOT}/bin/core3-swgemu"
if [[ "${DRY_RUN}" == "0" ]]; then
  mkdir -p /tmp/lbg-precu-from-246
  rsync -a -e "ssh ${SSH_OPTS[*]}" \
    --exclude 'bin/log/' \
    --exclude 'bin/databases/' \
    "${VM_USER}@${PRIME_HOST}:${STOCK_ROOT}/" \
    "/tmp/lbg-precu-from-246/"
  rsync -a -e "ssh ${SSH_OPTS[*]}" \
    "/tmp/lbg-precu-from-246/" \
    "${VM_USER}@${PRECU_HOST}:${STOCK_ROOT}/"
fi

echo "=== 4) Sync Prime → ${PRIME_HOST} (sans logs ni build, via ${PRECU_HOST}) ==="
if [[ "${DRY_RUN}" == "0" ]]; then
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "sudo mkdir -p /opt/lbg-new-mmo /opt/lbg-new-mmo-clean /opt/lbg-antigravity /opt/LBG_IA_MMO ${TRE_PATH} && sudo chown -R ${VM_USER}:${VM_USER} /opt/lbg-new-mmo /opt/lbg-new-mmo-clean /opt/lbg-antigravity /opt/LBG_IA_MMO ${TRE_PATH} 2>/dev/null || true"
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "bash -s" <<EOF
set -euo pipefail
RSYNC_EX=(--exclude 'MMOCoreORB/bin/log/' --exclude 'MMOCoreORB/build/' --exclude 'MMOCoreORB/bin/core3-clean.bak.*' --exclude 'MMOCoreORB/bin/databases.bak.*' --exclude 'build/')
if [[ -d /opt/lbg-new-mmo-clean ]]; then
  rsync -a "\${RSYNC_EX[@]}" -e "ssh -o StrictHostKeyChecking=no" /opt/lbg-new-mmo-clean/ ${VM_USER}@${PRIME_HOST}:/opt/lbg-new-mmo-clean/
fi
if [[ -d /opt/lbg-antigravity ]]; then
  rsync -a --exclude 'build/' -e "ssh -o StrictHostKeyChecking=no" /opt/lbg-antigravity/ ${VM_USER}@${PRIME_HOST}:/opt/lbg-antigravity/ || true
fi
if [[ -d /opt/LBG_IA_MMO ]]; then
  rsync -a --exclude '.venv/' --exclude '__pycache__/' -e "ssh -o StrictHostKeyChecking=no" /opt/LBG_IA_MMO/ ${VM_USER}@${PRIME_HOST}:/opt/LBG_IA_MMO/ || true
fi
rsync -a -e "ssh -o StrictHostKeyChecking=no" ${TRE_PATH}/ ${VM_USER}@${PRIME_HOST}:${TRE_PATH}/
echo "rsync Prime terminé depuis ${PRECU_HOST}"
EOF
fi

echo "=== 5) Config Prime ${PRIME_HOST} (DB distante ${DB_HOST}) ==="
_run scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime.service" \
  "${VM_USER}@${PRIME_HOST}:/tmp/lbg-core3-prime.service"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
CONF="${CLEAN_ROOT}/bin/conf/config-local.lua"
DBPASS="123456"
if [[ -f "${CLEAN_ROOT}/bin/conf/config-local.lua" ]]; then
  DBPASS=\$(grep -E '^Core3\\.DBPass' "${CLEAN_ROOT}/bin/conf/config-local.lua" 2>/dev/null | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1 || true)
fi
mkdir -p "${CLEAN_ROOT}/bin/log" "${CLEAN_ROOT}/bin/databases"
cat > "\${CONF}" <<LUA
-- Prime VM ${PRIME_HOST} — split_prime_246_precu_245_vm.sh
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
Core3.LoginPort = 44553
Core3.PingPort = 44562
Core3.ORBPort = 44519
Core3.StatusPort = 44555
Core3.WebPorts = 44560
Core3.ZoneGalaxyID = 3
LUA
chmod +x "${CLEAN_ROOT}/bin/core3-clean" 2>/dev/null || true
sudo cp /tmp/lbg-core3-prime.service /etc/systemd/system/
# Prime seul : ne plus tuer PreCU (autre VM)
sudo mkdir -p /etc/systemd/system/lbg-core3-prime.service.d
sudo tee /etc/systemd/system/lbg-core3-prime.service.d/no-precu-kill.conf >/dev/null <<'DROP'
[Service]
ExecStartPre=
DROP
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-prime.service
EOF

echo "=== 6) Config PreCU ${PRECU_HOST} ==="
_run scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-precu.service" \
  "${VM_USER}@${PRECU_HOST}:/tmp/lbg-core3-precu.service"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "bash -s" <<EOF
set -euo pipefail
CONF="${STOCK_ROOT}/bin/conf/config-local.lua"
DBPASS="123456"
if [[ -f "\${CONF}" ]]; then
  DBPASS=\$(grep -E '^Core3\\.DBPass' "\${CONF}" 2>/dev/null | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1 || true)
fi
mkdir -p "${STOCK_ROOT}/bin/log"
cat > "\${CONF}" <<LUA
-- PreCU VM ${PRECU_HOST} — split_prime_246_precu_245_vm.sh
Core3.TrePath = "${TRE_PATH}"
Core3.DBHost = "127.0.0.1"
Core3.DBPort = 3306
Core3.DBName = "swgemu"
Core3.DBUser = "swgemu"
Core3.DBPass = "\${DBPASS}"
Core3.MantisHost = "127.0.0.1"
Core3.MantisPort = 3306
Core3.MantisName = "swgemu"
Core3.MantisUser = "swgemu"
Core3.MantisPass = "\${DBPASS}"
LUA
chmod +x "${STOCK_ROOT}/bin/core3-swgemu"
sudo cp /tmp/lbg-core3-precu.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-precu.service
EOF

echo "=== 7) SQL galaxies (sur ${DB_HOST}) ==="
_run scp -q "${SSH_OPTS[@]}" \
  "${ROOT_DIR}/infra/snippets/core3-galaxy-prime-lan246.sql" \
  "${ROOT_DIR}/infra/snippets/core3-galaxy-precu-lan245.sql" \
  "${VM_USER}@${PRECU_HOST}:/tmp/"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" \
  "sudo mysql swgemu < /tmp/core3-galaxy-prime-lan246.sql && sudo mysql swgemu < /tmp/core3-galaxy-precu-lan245.sql"

echo "=== 8) Nettoyage Prime sur ${PRECU_HOST} ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" "bash -s" <<'EOF'
sudo systemctl stop lbg-core3-ia-sidecar.service lbg-core3-ia-bot-client.service lbg-core3-account-admin.service 2>/dev/null || true
sudo systemctl disable lbg-core3-prime.service 2>/dev/null || true
sudo rm -rf /opt/lbg-new-mmo-clean /opt/lbg-antigravity
# Conserver LBG_IA_MMO minimal si besoin admin ; sinon retirer services IA lourds
pkill -x core3-clean 2>/dev/null || true
pkill -f core3_ia_sidecar 2>/dev/null || true
df -h / | tail -1
EOF

echo "=== 9) Nettoyage PreCU sur ${PRIME_HOST} ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" "bash -s" <<'EOF'
sudo rm -rf /opt/lbg-new-mmo
pkill -x core3-swgemu 2>/dev/null || true
df -h / | tail -1
EOF

echo "=== 10) Démarrage services ==="
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRIME_HOST}" \
  "sudo systemctl restart lbg-core3-prime.service; sleep 3; systemctl is-active lbg-core3-prime.service; pgrep -a core3-clean || true"
_run ssh "${SSH_OPTS[@]}" "${VM_USER}@${PRECU_HOST}" \
  "sudo systemctl restart lbg-core3-precu.service; sleep 3; systemctl is-active lbg-core3-precu.service; pgrep -a core3-swgemu || true"

echo ""
echo "=== Terminé ==="
echo "  Prime : ${PRIME_HOST} — login UDP 44553, galaxie 3"
echo "  PreCU : ${PRECU_HOST} — login UDP 44453, galaxie 2"
echo "  MariaDB : ${DB_HOST}"
echo "  Suivi : bash infra/scripts/truncate_core3_logs_vm.sh both"
echo "          LBG_NEW_MMO_VM_HOST=${PRIME_HOST} bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
