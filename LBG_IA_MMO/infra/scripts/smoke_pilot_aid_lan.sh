#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — gameplay v1 (monde) via backend, sans LLM.
#
# 1) GET /v1/pilot/mmo-server/world-lyra (backend proxy) -> snapshot "avant" (jauges + réputation)
# 2) POST /v1/pilot/aid -> applique deltas (jauges + réputation) via mmo_server interne
# 3) GET /v1/pilot/mmo-server/world-lyra -> snapshot "après" (attend une variation cohérente)
#
# Variables :
#   LBG_LAN_HOST_CORE     défaut 192.168.0.140
#   LBG_BACKEND_PORT      défaut 8000
#   LBG_SMOKE_NPC_ID      défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S   défaut 30
#   LBG_PILOT_INTERNAL_TOKEN optionnel (sinon tentative lecture infra/secrets/lbg.env)
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"

read_env_var() {
  local key="$1"
  python3 - <<'PY' "$SEC_FILE" "$key"
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not p.exists():
    print("")
    raise SystemExit(0)
pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*\"?(.*?)\"?\s*$")
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    m = pat.match(line)
    if m:
        print(m.group(1).strip())
        raise SystemExit(0)
print("")
PY
}

if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

hdr_pilot=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_pilot=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

echo "=== Smoke LAN — pilot aid (sans LLM) ==="
echo "core=${CORE}:${BACKEND_PORT} npc=${NPC_ID} timeout_s=${TIMEOUT_S}"
if [[ -n "${PILOT_TOKEN}" ]]; then
  echo "pilot_token=SET"
else
  echo "pilot_token=EMPTY"
fi
echo ""

before="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/mmo-server/world-lyra" \
    --get --data-urlencode "npc_id=${NPC_ID}"
)"

BEFORE="${before}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["BEFORE"])
ly = j.get("lyra") or {}
g = ly.get("gauges") or {}
meta = ly.get("meta") or {}
rep = (meta.get("reputation") or {}).get("value", 0)
if not isinstance(g, dict) or not g:
    raise SystemExit(f"ERREUR: /v1/pilot/mmo-server/world-lyra ne contient pas lyra.gauges: {json.dumps(j, ensure_ascii=False)[:2000]}")
print("OK: before", "hunger=", g.get("hunger"), "thirst=", g.get("thirst"), "fatigue=", g.get("fatigue"), "rep=", rep)
PY

aid="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" \
    -H "content-type: application/json" \
    -d "{\"npc_id\":\"${NPC_ID}\",\"hunger_delta\":-0.2,\"thirst_delta\":-0.1,\"fatigue_delta\":-0.2,\"reputation_delta\":5}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/aid"
)"

OUT="${aid}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
if j.get("ok") is not True:
    raise SystemExit(f"ERREUR: /v1/pilot/aid a échoué: {json.dumps(j, ensure_ascii=False)[:2000]}")
wr = j.get("world_result") or {}
assert isinstance(wr, dict), "world_result dict attendu"
if wr.get("ok") is not True:
    raise SystemExit(f"ERREUR: mmo_server /aid a échoué: {json.dumps(wr, ensure_ascii=False)[:2000]}")
print("OK: aid applied")
PY

echo ""
after="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/mmo-server/world-lyra" \
    --get --data-urlencode "npc_id=${NPC_ID}"
)"

BEFORE="${before}" AFTER="${after}" python3 - <<'PY'
import json, os
b = json.loads(os.environ["BEFORE"])
a = json.loads(os.environ["AFTER"])
bg = (b.get("lyra") or {}).get("gauges") or {}
ag = (a.get("lyra") or {}).get("gauges") or {}
brep = int((((b.get("lyra") or {}).get("meta") or {}).get("reputation") or {}).get("value") or 0)
arep = int((((a.get("lyra") or {}).get("meta") or {}).get("reputation") or {}).get("value") or 0)
assert arep == brep + 5 or arep == 100, f"rep attendu +5 (borné), reçu {brep}->{arep}"

def f(x):
    try: return float(x)
    except Exception: return 0.0

# Les jauges augmentent lentement au tick; on attend un effet net négatif.
assert f(ag.get("hunger")) < f(bg.get("hunger")), "hunger attendu en baisse"
assert f(ag.get("thirst")) < f(bg.get("thirst")), "thirst attendu en baisse"
assert f(ag.get("fatigue")) < f(bg.get("fatigue")), "fatigue attendu en baisse"
print("OK: after gauges decreased + rep increased")
PY

echo ""
echo "Smoke pilot aid (LAN) : OK"

