#!/usr/bin/env bash
set -euo pipefail

# Recette LAN — jalon MMO v1 gameplay #1 (sans LLM).
#
# Définition (boucle minimale + interaction mesurable) :
#   - Interaction joueur→monde : « soin / don » = deltas aid (faim/soif/fatigue/réputation).
#   - Mesure : snapshot Lyra monde avant/après (jauges ↓, réputation +Δ bornée).
#   - Variante orchestrateur : intention world_aid + commit accepté côté WS.
#
# Enchaîne :
#   1) smoke_pilot_aid_lan.sh   — HTTP pilot → mmo_server (GET world-lyra → POST /v1/pilot/aid → GET)
#   2) smoke_commit_aid_lan.sh — POST /v1/pilot/route + context.world_action → world_aid → commit
#
# Variables : héritées des scripts appelés (LBG_LAN_HOST_CORE, LBG_PILOT_INTERNAL_TOKEN, etc.).
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Recette LAN — MMO v1 gameplay jalon #1 (observe → aid → observe + route world_aid) ==="
echo ""

bash "${ROOT_DIR}/infra/scripts/smoke_pilot_aid_lan.sh"
echo ""
bash "${ROOT_DIR}/infra/scripts/smoke_commit_aid_lan.sh"

echo ""
echo "Recette MMO v1 gameplay jalon #1 (LAN) : OK"
