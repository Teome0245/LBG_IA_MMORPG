#!/usr/bin/env bash
# Démo Prime — écrit une séquence de commandes dans ia_bridge/pending.jsonl sur la VM.
#
# Usage :
#   bash infra/scripts/demo_core3_prime_pending_vm.sh
#   bash infra/scripts/demo_core3_prime_pending_vm.sh --buyer Teome

set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CLEAN_BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
BUYER="Teome"

for arg in "$@"; do
  case "$arg" in
    --buyer) shift; BUYER="${1:-Teome}"; shift || true ;;
  esac
done

PENDING="${CLEAN_BIN}/ia_bridge/pending.jsonl"

echo "=== Demo pending.jsonl → ${VM_USER}@${VM_HOST} (buyer=${BUYER}) ==="

ssh "${VM_USER}@${VM_HOST}" "BUYER='${BUYER}' CLEAN_BIN='${CLEAN_BIN}' bash -s" <<'EOF'
set -euo pipefail
PENDING="${CLEAN_BIN}/ia_bridge/pending.jsonl"
mkdir -p "${CLEAN_BIN}/ia_bridge"
touch "${PENDING}"

{
  echo "npc_say|npc:core3_scribe|tatooine|0|0|0|Demo Prime — archives ouvertes."
  echo "offer_quest|npc:core3_vex_sorn|tatooine|0|0|0|${BUYER}|quest:mos_delivery_water"
  echo "interact|Lia|tatooine|0|0|0|quest_accept:${BUYER}:quest:mos_delivery_water"
  echo "vendor_buy|npc:core3_scribe|tatooine|0|0|0|${BUYER}|0"
  echo "craft_combine|Lia|tatooine|0|0|0|craft:mos_ration_pack"
  echo "interact|Lia|tatooine|0|0|0|quest_turnin:${BUYER}:quest:mos_delivery_water"
  echo "housing_enter|Lia|tatooine|0|0|0|"
} >> "${PENDING}"

echo "Lignes ajoutées :"
tail -n 8 "${PENDING}"
echo ""
echo "Attendre ~20s (tick 2s) puis vérifier :"
echo "  tail -f ${CLEAN_BIN}/ia_bridge/quest_state.jsonl"
echo "  tail -f ${CLEAN_BIN}/ia_bridge/events.jsonl"
EOF

echo "=== Demo envoyée ==="
