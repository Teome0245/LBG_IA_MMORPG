#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — "nouveaux PNJ" :
# 1) vérifie que le `mmo_server` expose /v1/world/lyra pour tous les PNJ du seed (mode strict)
# 2) vérifie que le backend /v1/pilot/route fonctionne sur les nouveaux PNJ (trace_id + lyra_meta.source)
#
# Usage :
#   bash infra/scripts/smoke_new_npcs_lan.sh
#
# Variables (relayées aux sous-smokes) :
#   LBG_LAN_HOST_CORE, LBG_BACKEND_PORT, LBG_SMOKE_TIMEOUT_S
#   LBG_LAN_HOST_MMO, LBG_MMO_HTTP_PORT
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Smoke LAN — nouveaux PNJ ==="
echo ""

echo "== 1/2) Seed mmo_server (strict) =="
LBG_SMOKE_STRICT=1 bash "${ROOT_DIR}/infra/scripts/smoke_mmo_seed_npcs_lan.sh"

echo ""
echo "== 2/2) Pilot route nouveaux PNJ =="
bash "${ROOT_DIR}/infra/scripts/smoke_pilot_route_new_npcs_lan.sh"

echo ""
echo "Smoke LAN nouveaux PNJ : OK"

