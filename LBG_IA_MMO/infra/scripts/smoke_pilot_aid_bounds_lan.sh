#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — bornage / erreurs attendues pour /v1/pilot/aid (sans LLM).
#
# 1) Appel invalide (delta hors bornes) -> attend HTTP != 200
# 2) Clamp : appliquer -1 sur jauges et +100 rep (borné) puis relire world-lyra
#
# Variables :
#   LBG_LAN_HOST_CORE       défaut 192.168.0.140
#   LBG_BACKEND_PORT        défaut 8000
#   LBG_SMOKE_NPC_ID        défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S     défaut 30
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

echo "=== Smoke LAN — pilot aid bounds (sans LLM) ==="
echo "core=${CORE}:${BACKEND_PORT} npc=${NPC_ID} timeout_s=${TIMEOUT_S}"
echo ""

echo "== 1) delta hors bornes (attend erreur) =="
code="$(
  curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" -H "content-type: application/json" \
    -d "{\"npc_id\":\"${NPC_ID}\",\"hunger_delta\":2.0}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/aid" || echo "000"
)"
if [[ "${code}" == "200" ]]; then
  echo "ERREUR: attendu HTTP != 200, reçu 200" >&2
  exit 1
fi
echo "OK: HTTP ${code}"
echo ""

echo "== 2) clamp jauges -> 0 et rep -> +100 (borné) =="
aid="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" -H "content-type: application/json" \
    -d "{\"npc_id\":\"${NPC_ID}\",\"hunger_delta\":-1.0,\"thirst_delta\":-1.0,\"fatigue_delta\":-1.0,\"reputation_delta\":100}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/aid"
)"
OUT="${aid}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, f"ok attendu true, reçu {j.get('ok')}"
print("OK: aid applied")
PY

echo ""
snap="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/mmo-server/world-lyra" \
    --get --data-urlencode "npc_id=${NPC_ID}"
)"
OUT="${snap}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
ly = j.get("lyra") or {}
g = ly.get("gauges") or {}
meta = ly.get("meta") or {}
rep = int(((meta.get("reputation") or {}).get("value") or 0))
assert float(g.get("hunger", 0.0)) <= 0.001
assert float(g.get("thirst", 0.0)) <= 0.001
assert float(g.get("fatigue", 0.0)) <= 0.001
assert -100 <= rep <= 100
print("OK: clamps ok (gauges≈0, rep bounded)")
PY

echo ""
echo "Smoke pilot aid bounds (LAN) : OK"

