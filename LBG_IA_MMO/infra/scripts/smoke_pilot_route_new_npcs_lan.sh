#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — dialogue PNJ via backend : /v1/pilot/route doit injecter Lyra (lyra_meta) et renvoyer trace_id.
#
# Usage:
#   bash infra/scripts/smoke_pilot_route_new_npcs_lan.sh
#
# Variables :
#   LBG_LAN_HOST_CORE défaut 192.168.0.140
#   LBG_BACKEND_PORT  défaut 8000
#   LBG_SMOKE_TIMEOUT_S défaut 120
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
PORT="${LBG_BACKEND_PORT:-8000}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"

NPC_IDS=("npc:healer" "npc:alchemist" "npc:mayor")

echo "== 0) backend healthz (${CORE}:${PORT}) =="
code="$(
  curl -sS --connect-timeout 2 --max-time 4 -o /dev/null -w "%{http_code}" \
    "http://${CORE}:${PORT}/healthz" || echo "000"
)"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: backend non joignable (HTTP ${code}) : http://${CORE}:${PORT}/healthz" >&2
  exit 1
fi
echo "OK: healthz=200"

echo ""
echo "== 1) /v1/pilot/route (nouveaux PNJ) =="
for npc_id in "${NPC_IDS[@]}"; do
  echo "-- ${npc_id}"
  out="$(
    curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
      -H "content-type: application/json" \
      -d "{\"actor_id\":\"p:smoke\",\"text\":\"Bonjour\",\"context\":{\"world_npc_id\":\"${npc_id}\",\"npc_name\":\"${npc_id}\",\"history\":[]}}" \
      "http://${CORE}:${PORT}/v1/pilot/route"
  )"
  OUT="${out}" NPC_ID="${npc_id}" python3 - <<'PY'
import json, os

raw = os.environ.get("OUT", "")
npc = os.environ.get("NPC_ID", "")

try:
    j = json.loads(raw)
except Exception as e:
    raise SystemExit(f"ERREUR: sortie non-JSON pour {npc}: {e}")

assert j.get("ok") is True, f"ERREUR: ok attendu true pour {npc}, reçu: {j.get('ok')}"
tid = (j.get("trace_id") or "").strip()
assert tid, f"ERREUR: trace_id non vide attendu pour {npc}"
meta = j.get("lyra_meta")
assert isinstance(meta, dict), f"ERREUR: lyra_meta dict attendu pour {npc}, reçu: {type(meta).__name__}"
src = (meta.get("source") or "").strip()
assert src in ("mmmorpg_ws", "mmo_world"), f"ERREUR: lyra_meta.source inattendue pour {npc}: {src!r}"
print(f"OK: {npc} trace_id=... lyra_meta.source={src}")
PY
done

echo ""
echo "Smoke pilot route nouveaux PNJ (LAN) : OK"

