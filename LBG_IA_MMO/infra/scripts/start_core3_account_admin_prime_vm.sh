#!/usr/bin/env bash
# Déploie l'UI comptes Core3 sur la VM Prime (246), port 8792.
# Même token que l'UI PreCU (245) par défaut.
#
# Usage :
#   bash infra/scripts/start_core3_account_admin_prime_vm.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT}/tools/core3_account_admin"
VM_HOST="${LBG_ACCOUNT_ADMIN_PRIME_VM_HOST:-192.168.0.246}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
REMOTE_DIR="/home/lbg/tools/core3_account_admin"
TOKEN="${CORE3_ADMIN_TOKEN:-lbg-core3-admin-change-me}"
DB_PASS="${CORE3_DB_PASS:-123456}"

echo "Sync UI Prime → ${VM_USER}@${VM_HOST}:${REMOTE_DIR}"
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${REMOTE_DIR}"
rsync -az --delete \
  "${TOOL}/core3_account_admin.py" \
  "${TOOL}/requirements.txt" \
  "${TOOL}/README.md" \
  "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/"

scp -q "${ROOT}/infra/systemd/lbg-core3-account-admin-prime.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-account-admin-prime.service"
scp -q "${ROOT}/infra/snippets/core3-mysql-precu-245-allow-prime-admin.sql" \
  "${VM_USER}@${PRECU_HOST}:/tmp/" 2>/dev/null || true

ssh "${VM_USER}@${PRECU_HOST}" "sudo mysql < /tmp/core3-mysql-precu-245-allow-prime-admin.sql" 2>/dev/null || true

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
if ! python3 -c 'import pymysql' 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-pymysql 2>/dev/null \
    || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip
  python3 -m pip install --user -q pymysql 2>/dev/null || pip3 install --user -q pymysql
fi
cd "${REMOTE_DIR}"
sudo tee /etc/lbg-core3-account-admin.env >/dev/null <<ENV
CORE3_DB_PASS=${DB_PASS}
CORE3_ADMIN_TOKEN=${TOKEN}
CORE3_PRECU_DB_PASS=${DB_PASS}
ENV
sudo cp /tmp/lbg-core3-account-admin-prime.service /etc/systemd/system/lbg-core3-account-admin.service
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-account-admin.service
sudo systemctl restart lbg-core3-account-admin.service
sleep 1
systemctl is-active lbg-core3-account-admin.service
EOF

echo "UI Prime : http://${VM_HOST}:8792/"
echo "Token    : ${TOKEN}"
