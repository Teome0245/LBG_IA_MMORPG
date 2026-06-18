#!/usr/bin/env bash
# Phase D — installe core3client + config + unité systemd (VM 245).
# Usage : bash infra/scripts/install_core3_ia_bot_client_vm.sh [--enable] [--build]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
DO_ENABLE=0
DO_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --enable) DO_ENABLE=1 ;;
    --build) DO_BUILD=1 ;;
  esac
done

echo "=== Phase D core3client → ${VM_USER}@${VM_HOST} ==="

scp -q "${ROOT_DIR}/content/core3/ia_bridge/lia_bot_session.json" \
  "${ROOT_DIR}/infra/snippets/.env-core3client.example" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${ROOT_DIR}/infra/scripts/install_core3_ia_bot_client_vm.sh" \
  "${VM_USER}@${VM_HOST}:/tmp/"

scp -q "${ROOT_DIR}/infra/systemd/lbg-core3-ia-bot-client.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-ia-bot-client.service"

ssh "${VM_USER}@${VM_HOST}" "DO_BUILD=${DO_BUILD} DO_ENABLE=${DO_ENABLE} bash -s" <<'EOF'
set -euo pipefail
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin
BUILD=/opt/lbg-new-mmo-clean/MMOCoreORB/build

if [[ "${DO_BUILD}" == "1" ]]; then
  echo "Build core3client..."
  cmake --build "${BUILD}" --target core3client -j"$(nproc)"
  cp -f "${BUILD}/src/client/core3client" "${BIN}/core3client"
  chmod +x "${BIN}/core3client"
fi

if [[ ! -x "${BIN}/core3client" ]]; then
  if [[ -x "${BUILD}/src/client/core3client" ]]; then
    cp -f "${BUILD}/src/client/core3client" "${BIN}/core3client"
  else
    echo "ERROR: core3client absent — relancer avec --build" >&2
    exit 1
  fi
fi

sudo mkdir -p "${BIN}/ia_bridge" /opt/LBG_IA_MMO/infra/scripts
sudo cp /tmp/lia_bot_session.json "${BIN}/ia_bridge/lia_bot_session.json"
sudo cp /tmp/run_core3_ia_bot_client_vm.sh /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chown lbg:lbg "${BIN}/ia_bridge/lia_bot_session.json"

if [[ ! -f "${BIN}/.env-core3client" ]]; then
  sudo cp /tmp/.env-core3client.example "${BIN}/.env-core3client"
  sudo chown lbg:lbg "${BIN}/.env-core3client"
  sudo chmod 600 "${BIN}/.env-core3client"
  echo "Cree ${BIN}/.env-core3client (verifier mot de passe)"
fi

sudo cp /tmp/lbg-core3-ia-bot-client.service /etc/systemd/system/lbg-core3-ia-bot-client.service
sudo systemctl daemon-reload

if [[ "${DO_ENABLE}" == "1" ]]; then
  sudo systemctl enable lbg-core3-ia-bot-client.service
  sudo systemctl restart lbg-core3-ia-bot-client.service
  sleep 2
  systemctl is-active lbg-core3-ia-bot-client.service || true
  systemctl status lbg-core3-ia-bot-client.service --no-pager | head -15
else
  echo "Unit installee. Activer : sudo systemctl enable --now lbg-core3-ia-bot-client"
fi

"${BIN}/core3client" --help | head -3
echo "OK Phase D fichiers installes"
EOF

echo ""
echo "Test manuel VM :"
echo "  ssh ${VM_USER}@${VM_HOST} 'bash /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh --login-only'"
echo "Doc : ${ROOT_DIR}/docs/core3_ia_phase_d_headless_bot.md"
