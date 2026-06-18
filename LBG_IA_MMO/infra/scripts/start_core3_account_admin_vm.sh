#!/usr/bin/env bash
# Démarre l'UI web de gestion des comptes Core3 sur la VM (port 8792).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT}/tools/core3_account_admin"
# UI comptes + MariaDB sur 245 ; sonde Prime sur 246 (split juin 2026).
VM_HOST="${LBG_ACCOUNT_ADMIN_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
REMOTE_DIR="/home/lbg/tools/core3_account_admin"
TOKEN="${CORE3_ADMIN_TOKEN:-lbg-core3-admin-change-me}"

echo "Sync → ${VM_USER}@${VM_HOST}:${REMOTE_DIR}"
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${REMOTE_DIR}"
rsync -az --delete \
  "${TOOL}/core3_account_admin.py" \
  "${TOOL}/requirements.txt" \
  "${TOOL}/README.md" \
  "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/"
scp -q "${ROOT}/infra/systemd/lbg-core3-account-admin.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-account-admin.service"

PRIME_HOST="${CORE3_PRIME_STATUS_HOST:-192.168.0.246}"
SETUP="${ROOT}/infra/scripts/remote_setup_account_admin.sh"

scp -q "${SETUP}" "${VM_USER}@${VM_HOST}:/tmp/remote_setup_account_admin.sh"
ssh "${VM_USER}@${VM_HOST}" \
  "PRIME_HOST='${PRIME_HOST}' REMOTE_DIR='${REMOTE_DIR}' TOKEN='${TOKEN}' VM_HOST='${VM_HOST}' bash /tmp/remote_setup_account_admin.sh"
