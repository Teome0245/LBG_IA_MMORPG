#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — commit E2E via backend (nouveaux PNJ).
# Enchaîne `infra/scripts/smoke_commit_dialogue.sh` sur plusieurs PNJ et échoue au premier KO.
#
# Usage:
#   bash infra/scripts/smoke_commit_dialogue_new_npcs_lan.sh
#
# Variables (relayées) :
#   LBG_LAN_HOST_CORE, LBG_LAN_HOST_MMO, LBG_MMMORPG_INTERNAL_PORT, LBG_MMMORPG_INTERNAL_HTTP_TOKEN
#   LBG_SMOKE_TEXT
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SMOKE="${ROOT_DIR}/infra/scripts/smoke_commit_dialogue.sh"

NPCS=("npc:mayor" "npc:healer" "npc:alchemist")

echo "=== Smoke LAN — commit dialogue (nouveaux PNJ) ==="
echo ""

for npc_id in "${NPCS[@]}"; do
  echo "== ${npc_id} =="
  LBG_SMOKE_NPC_ID="${npc_id}" bash "${SMOKE}"
  echo ""
done

echo "Smoke commit dialogue nouveaux PNJ (LAN) : OK"

