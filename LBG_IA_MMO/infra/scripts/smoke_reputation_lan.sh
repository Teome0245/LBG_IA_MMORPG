#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — réputation locale (sans LLM).
#
# 1) POST /v1/pilot/reputation (backend) -> commit reputation_delta
# 2) GET snapshot interne (mmmorpg_server) -> vérifie que lyra.meta.reputation.value a changé
#
# Usage:
#   bash infra/scripts/smoke_reputation_lan.sh
#
# Variables :
#   LBG_LAN_HOST_CORE          défaut 192.168.0.140
#   LBG_BACKEND_PORT           défaut 8000
#   LBG_LAN_HOST_MMO           défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT  défaut 8773
#   LBG_SMOKE_NPC_ID           défaut npc:merchant
#   LBG_SMOKE_REP_DELTA        défaut 11
#   LBG_SMOKE_TIMEOUT_S        défaut 30
#   LBG_SMOKE_RESET_REP        défaut 0 ; si 1, remet la réputation à 0 avant le test (best-effort)
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (sinon lecture infra/secrets/lbg.env)
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
INT_PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
DELTA="${LBG_SMOKE_REP_DELTA:-11}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
RESET_REP="${LBG_SMOKE_RESET_REP:-0}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
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

if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_MMMORPG_INTERNAL_HTTP_TOKEN")"
fi
if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

hdr_pilot=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_pilot=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

echo "=== Smoke LAN — réputation (sans LLM) ==="
echo "core=${CORE}:${BACKEND_PORT} mmo=${MMO}:${INT_PORT} npc=${NPC_ID} delta=${DELTA} timeout_s=${TIMEOUT_S} reset_rep=${RESET_REP}"
echo ""

snap_url="http://${MMO}:${INT_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_rep_before"
echo "== 1) Snapshot avant =="
before="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" "${snap_url}"
)"
echo "${before}" | head -c 500
echo ""

before_v="$(
  OUT="${before}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
meta = (j.get("lyra") or {}).get("meta") or {}
rep = meta.get("reputation") or {}
v = rep.get("value")
print(int(v) if v is not None else 0)
PY
)"
echo "reputation_before=${before_v}"

echo ""
if [[ "${RESET_REP}" == "1" ]]; then
  if [[ "${before_v}" != "0" ]]; then
    echo "== 2a) Reset réputation -> 0 (delta = -before) =="
    reset_delta="$((0 - before_v))"
    reset_out="$(
      curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
        "${hdr_pilot[@]}" \
        -H "content-type: application/json" \
        -d "{\"npc_id\":\"${NPC_ID}\",\"delta\":${reset_delta}}" \
        "http://${CORE}:${BACKEND_PORT}/v1/pilot/reputation"
    )"
    OUT="${reset_out}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, "reset: ok attendu true"
cr = j.get("commit_result") or {}
assert cr.get("ok") is True and cr.get("accepted") is True, "reset: commit_result attendu ok+accepted"
print("OK: reset applied")
PY
    echo ""
    echo "== 2b) Snapshot après reset =="
    after_reset="$(
      curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" \
        "http://${MMO}:${INT_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_rep_reset"
    )"
    reset_v="$(
      OUT="${after_reset}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
meta = (j.get("lyra") or {}).get("meta") or {}
rep = meta.get("reputation") or {}
print(int(rep.get("value") or 0))
PY
    )"
    if [[ "${reset_v}" != "0" ]]; then
      echo "ERREUR: reset attendu 0, reçu ${reset_v}" >&2
      exit 1
    fi
    echo "OK: reputation_reset=0"
    before_v="0"
  else
    echo "Reset demandé mais déjà à 0 : OK"
  fi
  echo ""
fi

echo "== 2) Commit delta via backend (/v1/pilot/reputation) =="
commit="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" \
    -H "content-type: application/json" \
    -d "{\"npc_id\":\"${NPC_ID}\",\"delta\":${DELTA}}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/reputation"
)"
echo "${commit}" | head -c 800
echo ""

OUT="${commit}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, f"ok=true attendu, reçu {j.get('ok')}"
cr = j.get("commit_result") or {}
assert cr.get("ok") is True, f"commit_result.ok attendu true, reçu {cr.get('ok')}"
assert cr.get("accepted") is True, f"accepted attendu true, reçu {cr.get('accepted')}"
print("OK: commit accepted")
PY

echo ""
echo "== 3) Snapshot après (doit refléter la variation) =="
after="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" \
    "http://${MMO}:${INT_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_rep_after"
)"
echo "${after}" | head -c 500
echo ""

BEFORE="${before_v}" DELTA="${DELTA}" OUT="${after}" python3 - <<'PY'
import json, os
before = int(os.environ["BEFORE"])
delta = int(os.environ["DELTA"])
j = json.loads(os.environ["OUT"])
meta = (j.get("lyra") or {}).get("meta") or {}
rep = meta.get("reputation") or {}
v = int(rep.get("value") or 0)
expected = before + delta
if expected < -100: expected = -100
if expected > 100: expected = 100
assert v == expected, f"reputation attendu {expected}, reçu {v}"
print(f"OK: reputation_after={v}")
PY

echo ""
echo "Smoke réputation (LAN) : OK"

