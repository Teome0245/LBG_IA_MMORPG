#!/usr/bin/env bash
# Configure le routage LLM du sidecar pont IA (aligné agents / lbg-ia-mmo.env).
#
# Usage :
#   bash infra/scripts/configure_core3_ia_llm_vm.sh          # auto (défaut)
#   bash infra/scripts/configure_core3_ia_llm_vm.sh fast
#   bash infra/scripts/configure_core3_ia_llm_vm.sh local
#
# Prérequis VM 245 : /etc/lbg-ia-mmo.env avec LBG_DIALOGUE_FAST_* / GROQ_API_KEY, etc.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
TARGET="${1:-auto}"

scp -q "${ROOT_DIR}/tools/core3_ia_sidecar/core3_ia_sidecar.py" \
  "${ROOT_DIR}/content/core3/core3_npc_catalog.json" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-sidecar.service" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
TARGET="${TARGET}"

sudo cp /tmp/lbg-core3-ia-sidecar.service /etc/systemd/system/
sudo mkdir -p /opt/LBG_IA_MMO/content/core3
sudo cp /tmp/core3_ia_sidecar.py /opt/LBG_IA_MMO/tools/core3_ia_sidecar/core3_ia_sidecar.py
sudo cp /tmp/core3_npc_catalog.json /opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json
sudo chmod +x /opt/LBG_IA_MMO/tools/core3_ia_sidecar/core3_ia_sidecar.py

sudo tee /etc/lbg-core3-ia.env >/dev/null <<ENV
CORE3_IA_ZONE=tatooine
CORE3_IA_BOT_NAME=Bot_IA
CORE3_IA_BOT_CHARACTER=Lia
CORE3_IA_DIALOGUE_TARGET=\${TARGET}
CORE3_IA_AUTO_ORDER=fast
CORE3_IA_LLM_MAX_TOKENS=120
CORE3_IA_LLM_TIMEOUT_FAST=25
CORE3_IA_LLM_TIMEOUT_LOCAL=20
CORE3_IA_NPC_PILOTS_JSON=/opt/LBG_IA_MMO/content/core3/core3_npc_pilots.json
CORE3_IA_NPC_CATALOG_JSON=/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json
CORE3_IA_NPC_SNAPSHOTS_PATH=ia_bridge/npc_snapshots.json
ENV

sudo systemctl daemon-reload
sudo systemctl restart lbg-core3-ia-sidecar.service
sleep 1
curl -s http://127.0.0.1:8791/healthz
echo
EOF

echo "Routage LLM : CORE3_IA_DIALOGUE_TARGET=${TARGET} (clés via /etc/lbg-ia-mmo.env)"
echo "Smoke : bash infra/scripts/smoke_core3_ia_phase_b_lan.sh --with-think"
