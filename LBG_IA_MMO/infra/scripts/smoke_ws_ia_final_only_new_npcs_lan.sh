#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — WS → IA (final-only) sur nouveaux PNJ (trace_id non vide).
#
# Enchaîne `mmmorpg_server/tools/ws_ia_cli.py --final-only --json` sur plusieurs npc_id.
#
# Usage:
#   bash infra/scripts/smoke_ws_ia_final_only_new_npcs_lan.sh
#
# Variables :
#   LBG_LAN_HOST_MMO        défaut 192.168.0.245
#   LBG_MMMORPG_WS_PORT     défaut 7733
#   LBG_SMOKE_TIMEOUT_S     défaut 120
#   LBG_SMOKE_REPEAT        défaut 1
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${ROOT_DIR}/.venv/bin/python"
CLI="${ROOT_DIR}/mmmorpg_server/tools/ws_ia_cli.py"

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_WS_PORT:-7733}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"
REPEAT="${LBG_SMOKE_REPEAT:-1}"

if [[ ! -x "${PY}" ]]; then
  echo "ERREUR: venv introuvable: ${PY} (lance d'abord infra/scripts/install_local.sh)" >&2
  exit 1
fi

NPCS=("npc:mayor" "npc:healer" "npc:alchemist")

echo "=== Smoke LAN — ws_ia_cli final-only (nouveaux PNJ) ==="
echo "ws=ws://${MMO}:${PORT} timeout_s=${TIMEOUT_S} repeat=${REPEAT}"
echo ""

for npc_id in "${NPCS[@]}"; do
  echo "== ${npc_id} =="
  out="$(
    "${PY}" "${CLI}" \
      --ws "ws://${MMO}:${PORT}" \
      --player-name "smoke" \
      --npc-id "${npc_id}" \
      --npc-name "${npc_id}" \
      --text "Bonjour" \
      --timeout-s "${TIMEOUT_S}" \
      --repeat "${REPEAT}" \
      --sleep-ms 200 \
      --final-only \
      --json
  )"
  echo "${out}"
  OUT="${out}" NPC_ID="${npc_id}" python3 - <<'PY'
import json, os

raw = os.environ.get("OUT", "")
npc = os.environ.get("NPC_ID", "")
j = json.loads(raw)
assert j.get("ok") is True, f"ok attendu true pour {npc}, reçu: {j.get('ok')}"
assert int(j.get("n_ok") or 0) >= 1, f"n_ok>=1 attendu pour {npc}, reçu: {j.get('n_ok')}"
tid = (j.get("trace_id") or "").strip()
assert tid, f"trace_id final attendu non vide pour {npc}"
print(f"OK: {npc} trace_id=... n_ok={j.get('n_ok')}")
PY
  echo ""
done

echo "Smoke ws_ia final-only nouveaux PNJ (LAN) : OK"

