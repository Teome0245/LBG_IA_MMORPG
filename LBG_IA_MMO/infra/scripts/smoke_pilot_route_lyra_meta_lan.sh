#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — /v1/pilot/route expose Lyra dans la réponse (source monde)
#
# Vérifie que la réponse JSON contient result.output.lyra.meta.source parmi
# les sources attendues (snapshot WS interne ou fallback mmo_server).
#
# Usage :
#   bash infra/scripts/smoke_pilot_route_lyra_meta_lan.sh
#
# Variables :
#   LBG_LAN_HOST_CORE  défaut 192.168.0.140
#   LBG_SMOKE_NPC_ID   défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S défaut 120

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"

echo "== POST /v1/pilot/route (core=${CORE}, npc=${NPC_ID}) =="
out="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000/v1/pilot/route" \
    -H "content-type: application/json" \
    -d "{\"actor_id\":\"p:smoke_lyra_meta\",\"text\":\"Bonjour\",\"context\":{\"world_npc_id\":\"${NPC_ID}\",\"history\":[]}}"
)"
echo "${out}" | head -c 2000
echo ""

OUT="${out}" python3 - <<'PY'
import json
import os

allowed = {"mmmorpg_ws", "mmo_world"}
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, "ok=true attendu"
res = j.get("result")
assert isinstance(res, dict), "result attendu dict"
out = res.get("output")
assert isinstance(out, dict), "result.output attendu dict"
ly = out.get("lyra")
assert isinstance(ly, dict), "result.output.lyra attendu dict"
meta = ly.get("meta")
assert isinstance(meta, dict), "lyra.meta attendu dict"
src = (meta.get("source") or "").strip()
assert src in allowed, f"meta.source inattendu: {src!r} (attendu un de {sorted(allowed)})"
print(f"OK: result.output.lyra.meta.source={src!r}")
PY

echo ""
echo "Smoke pilot route Lyra meta (LAN) : OK"
