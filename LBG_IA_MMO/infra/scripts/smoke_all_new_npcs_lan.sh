#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — validation complète "nouveaux PNJ" (one-shot).
#
# Enchaîne :
# 1) reset seed `mmo_server` (DESTRUCTIF sur l’état persisté)
# 2) validation HTTP (seed strict + /v1/pilot/route nouveaux PNJ + commit E2E)
# 3) validation WS→IA (ws_ia_cli final-only nouveaux PNJ)
#
# Usage:
#   bash infra/scripts/smoke_all_new_npcs_lan.sh
#
# Variables relayées :
#   - reset seed : LBG_VM_HOST, LBG_VM_USER, LBG_MMO_UNIT, LBG_MMO_STATE_PATH
#   - HTTP/commit : LBG_LAN_HOST_CORE, LBG_LAN_HOST_MMO, LBG_BACKEND_PORT, LBG_MMO_HTTP_PORT, LBG_SMOKE_TIMEOUT_S
#   - WS→IA : LBG_MMMORPG_WS_PORT, LBG_SMOKE_TIMEOUT_S, LBG_SMOKE_REPEAT
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Smoke LAN — validation complète nouveaux PNJ (one-shot) ==="
echo ""

echo "== 1/2) Reset + validations HTTP/commit =="
bash "${ROOT_DIR}/infra/scripts/smoke_reset_seed_and_new_npcs_lan.sh"

echo ""
echo "== 2/2) WS→IA final-only (nouveaux PNJ) =="
bash "${ROOT_DIR}/infra/scripts/smoke_ws_ia_final_only_new_npcs_lan.sh"

echo ""
echo "Smoke ALL nouveaux PNJ (LAN) : OK"

