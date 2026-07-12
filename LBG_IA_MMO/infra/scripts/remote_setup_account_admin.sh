#!/usr/bin/env bash
# Exécuté sur la VM 245 par start_core3_account_admin_vm.sh (stdin via ssh bash -s).
set -euo pipefail

PRIME_HOST="${PRIME_HOST:-192.168.0.246}"
PRECU_HOST="${PRECU_HOST:-192.168.0.245}"
REMOTE_DIR="${REMOTE_DIR:-/home/lbg/tools/core3_account_admin}"
TOKEN="${TOKEN:-lbg-core3-admin-change-me}"
VM_HOST="${VM_HOST:-192.168.0.245}"
DB_PASS="${CORE3_DB_PASS:-123456}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ! -f ~/.ssh/id_ed25519 ]]; then
  ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q
fi
PUB="$(cat ~/.ssh/id_ed25519.pub)"
ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "lbg@${PRIME_HOST}" \
  "grep -qF \"${PUB}\" ~/.ssh/authorized_keys 2>/dev/null || echo \"${PUB}\" >> ~/.ssh/authorized_keys" || true

echo "=== MariaDB Prime : accès UI depuis ${PRECU_HOST} ==="
scp -q -o BatchMode=yes -o ConnectTimeout=5 \
  "${ROOT_DIR}/infra/snippets/core3-mysql-prime-246-allow-precu-admin.sql" \
  "lbg@${PRIME_HOST}:/tmp/" 2>/dev/null || true
ssh -o BatchMode=yes -o ConnectTimeout=8 "lbg@${PRIME_HOST}" "bash -s" <<EOF || true
set -euo pipefail
sudo tee /etc/mysql/mariadb.conf.d/99-lbg-bind-lan.cnf >/dev/null <<'CNF'
[mysqld]
bind-address = 0.0.0.0
CNF
sudo systemctl restart mariadb
sleep 2
sudo mysql < /tmp/core3-mysql-prime-246-allow-precu-admin.sql
EOF

cd "${REMOTE_DIR}"
python3 -m pip install --user -q -r requirements.txt 2>/dev/null || pip3 install --user -r requirements.txt -q

sudo tee /etc/lbg-core3-account-admin.env >/dev/null <<ENV
CORE3_DB_PASS=${DB_PASS}
CORE3_ADMIN_TOKEN=${TOKEN}
CORE3_PRIME_DB_HOST=${PRIME_HOST}
CORE3_PRIME_DB_PASS=${DB_PASS}
CORE3_PRIME_DB_ENABLED=1
CORE3_PRIME_STATUS_HOST=${PRIME_HOST}
CORE3_PRIME_CLIENT_IP=${PRIME_HOST}
CORE3_PRECU_CLIENT_IP=${PRECU_HOST}
ENV
sudo cp /tmp/lbg-core3-account-admin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-account-admin.service
sudo systemctl restart lbg-core3-account-admin.service
sleep 1
systemctl is-active lbg-core3-account-admin.service
echo "UI : http://${VM_HOST}:8792/"
echo "Token : ${TOKEN}"
