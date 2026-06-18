#!/usr/bin/env bash
# Phase F — installe la session headless du second joueur IA Nix (VM 245).
#
# Usage :
#   bash infra/scripts/install_core3_ia_bot_client_nix_vm.sh
#   bash infra/scripts/install_core3_ia_bot_client_nix_vm.sh --enable

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
DO_ENABLE=0

for arg in "$@"; do
  case "$arg" in
    --enable) DO_ENABLE=1 ;;
  esac
done

echo "=== Phase F Nix core3client → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/content/core3/ia_bridge/nix_bot_session.json" \
  "${ROOT_DIR}/content/core3/core3_ia_players.json" \
  "${ROOT_DIR}/content/core3/nix_scout_persona.json" \
  "${ROOT_DIR}/infra/snippets/.env-core3client-nix.example" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${VM_USER}@${VM_HOST}:/tmp/"

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-bot-client-nix.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-ia-bot-client-nix.service"

ssh "${VM_USER}@${VM_HOST}" "DO_ENABLE=${DO_ENABLE} bash -s" <<'EOF'
set -euo pipefail
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin

if [[ ! -x "${BIN}/core3client" ]]; then
  echo "ERROR: ${BIN}/core3client absent — installer Phase D Lia d'abord" >&2
  exit 1
fi

sudo mkdir -p "${BIN}/ia_bridge" /opt/LBG_IA_MMO/infra/scripts /opt/LBG_IA_MMO/content/core3
sudo cp /tmp/nix_bot_session.json "${BIN}/ia_bridge/nix_bot_session.json"
sudo cp /tmp/core3_ia_players.json /opt/LBG_IA_MMO/content/core3/core3_ia_players.json
sudo cp /tmp/nix_scout_persona.json /opt/LBG_IA_MMO/content/core3/nix_scout_persona.json
sudo cp /tmp/run_core3_ia_bot_client_vm.sh /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chown -R lbg:lbg "${BIN}/ia_bridge/nix_bot_session.json" /opt/LBG_IA_MMO/content/core3/core3_ia_players.json /opt/LBG_IA_MMO/content/core3/nix_scout_persona.json

if [[ ! -f "${BIN}/.env-core3client-nix" ]]; then
  sudo cp /tmp/.env-core3client-nix.example "${BIN}/.env-core3client-nix"
  sudo chown lbg:lbg "${BIN}/.env-core3client-nix"
  sudo chmod 600 "${BIN}/.env-core3client-nix"
  echo "Cree ${BIN}/.env-core3client-nix — renseigner CORE3_CLIENT_PASSWORD avant activation."
fi

sudo cp /tmp/lbg-core3-ia-bot-client-nix.service /etc/systemd/system/lbg-core3-ia-bot-client-nix.service
sudo systemctl daemon-reload

if [[ "${DO_ENABLE}" == "1" ]]; then
  if grep -q 'CHANGE_ME_BOT_IA_2' "${BIN}/.env-core3client-nix"; then
    echo "ERROR: ${BIN}/.env-core3client-nix contient encore CHANGE_ME_BOT_IA_2" >&2
    exit 2
  fi
  sudo systemctl enable lbg-core3-ia-bot-client-nix.service
  sudo systemctl restart lbg-core3-ia-bot-client-nix.service
  sleep 2
  systemctl is-active lbg-core3-ia-bot-client-nix.service || true
else
  echo "Unit Nix installee. Activer après mot de passe : sudo systemctl enable --now lbg-core3-ia-bot-client-nix"
fi

echo "OK Phase F Nix fichiers installes"
EOF

echo ""
echo "Test login-only (après mot de passe VM) :"
echo "  ssh ${VM_USER}@${VM_HOST} 'CORE3_IA_BOT_CHARACTER=Nix CORE3_CLIENT_ENV_FILE=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix CORE3_CLIENT_OPTIONS_JSON=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/nix_bot_session.json bash /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh --login-only'"
