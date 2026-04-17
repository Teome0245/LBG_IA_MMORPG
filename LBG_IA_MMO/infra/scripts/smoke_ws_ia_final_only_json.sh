#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — WS → pont IA → réponse finale (trace_id non vide), en mode JSON (automation/bench).
#
# Usage:
#   bash infra/scripts/smoke_ws_ia_final_only_json.sh
#
# Variables :
#   LBG_LAN_HOST_MMO   défaut 192.168.0.245
#   LBG_MMMORPG_WS_PORT défaut 7733
#   LBG_SMOKE_NPC_ID   défaut npc:merchant
#   LBG_SMOKE_NPC_NAME défaut "Marchand"
#   LBG_SMOKE_TEXT     défaut "Bonjour"
#   LBG_SMOKE_REPEAT   défaut 3
#   LBG_SMOKE_TIMEOUT_S défaut 120

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_WS_PORT:-7733}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
NPC_NAME="${LBG_SMOKE_NPC_NAME:-Marchand}"
TEXT="${LBG_SMOKE_TEXT:-Bonjour}"
REPEAT="${LBG_SMOKE_REPEAT:-3}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${ROOT_DIR}/.venv/bin/python"
CLI="${ROOT_DIR}/mmmorpg_server/tools/ws_ia_cli.py"

if [[ ! -x "${PY}" ]]; then
  echo "ERREUR: venv introuvable: ${PY} (lance d'abord infra/scripts/install_local.sh)" >&2
  exit 1
fi

echo "== ws_ia_cli final-only (JSON) =="
out="$(
  "${PY}" "${CLI}" \
    --ws "ws://${MMO}:${PORT}" \
    --player-name "smoke" \
    --npc-id "${NPC_ID}" \
    --npc-name "${NPC_NAME}" \
    --text "${TEXT}" \
    --timeout-s "${TIMEOUT_S}" \
    --repeat "${REPEAT}" \
    --sleep-ms 200 \
    --final-only \
    --json
)"
echo "${out}"

OUT="${out}" python3 - <<'PY'
import json, os

raw = os.environ.get("OUT", "")
try:
    j = json.loads(raw)
except Exception as e:
    raise SystemExit(f"ERREUR: sortie non-JSON: {e}")

assert isinstance(j, dict), "JSON doit être un objet"
assert j.get("ok") is True, f"ok attendu true, reçu: {j.get('ok')}"
assert int(j.get("n_ok") or 0) >= 1, f"n_ok>=1 attendu, reçu: {j.get('n_ok')}"
trace_id = (j.get("trace_id") or "").strip()
assert trace_id, "trace_id final attendu non vide"
for k in ("min_ms","p50_ms","p95_ms","max_ms"):
    v = j.get(k)
    assert isinstance(v, int) and v > 0, f"{k} attendu int>0, reçu: {v!r}"
print("OK: ws_ia_cli final-only JSON")
PY

echo ""
echo "Smoke ws_ia final-only JSON : OK"

