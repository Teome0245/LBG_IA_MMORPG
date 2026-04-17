#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — minimal, non destructif, sans LLM.
#
# Couvre :
# - healthz backend + orchestrator (core)
# - healthz + snapshot HTTP interne (mmmorpg_server sur VM MMO)
# - un appel backend /v1/pilot/internal/route qui force l’intent devops_probe (pas de LLM)
#
# Usage:
#   bash infra/scripts/smoke_lan_minimal.sh
#
# Variables :
#   LBG_LAN_HOST_CORE              défaut 192.168.0.140
#   LBG_BACKEND_PORT               défaut 8000
#   LBG_ORCHESTRATOR_PORT          défaut 8010
#   LBG_LAN_HOST_MMO               défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT      défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (header X-LBG-Service-Token) ; sinon tente lecture infra/secrets/lbg.env
#   LBG_PILOT_INTERNAL_TOKEN       optionnel (si le backend exige un token sur /v1/pilot/internal/route)
#   LBG_SMOKE_NPC_ID               défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S            défaut 30
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
ORCH_PORT="${LBG_ORCHESTRATOR_PORT:-8010}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
INT_PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"

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

TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_MMMORPG_INTERNAL_HTTP_TOKEN")"
fi

PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"
if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

hdr_snap=()
if [[ -n "${TOKEN}" ]]; then
  hdr_snap=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

hdr_pilot=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_pilot=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

curl_code() {
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" -o /dev/null -w "%{http_code}" "$@" || echo "000"
}

echo "=== Smoke LAN minimal (sans LLM) ==="
echo "core=${CORE}:${BACKEND_PORT} orch=${CORE}:${ORCH_PORT} mmo=${MMO} internal=${MMO}:${INT_PORT} timeout_s=${TIMEOUT_S}"
echo ""

echo "== 1) healthz backend =="
code="$(curl_code "http://${CORE}:${BACKEND_PORT}/healthz")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: backend healthz HTTP ${code}" >&2
  exit 1
fi
echo "OK: backend healthz=200"

echo ""
echo "== 2) healthz orchestrator =="
code="$(curl_code "http://${CORE}:${ORCH_PORT}/healthz")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: orchestrator healthz HTTP ${code}" >&2
  exit 1
fi
echo "OK: orchestrator healthz=200"

echo ""
echo "== 3) healthz mmmorpg HTTP interne =="
code="$(curl_code "${hdr_snap[@]}" "http://${MMO}:${INT_PORT}/healthz")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: mmmorpg internal healthz HTTP ${code} (token manquant ? port ?)" >&2
  exit 1
fi
echo "OK: internal healthz=200"

echo ""
echo "== 4) snapshot interne (trace_id fixe) =="
snap_url="http://${MMO}:${INT_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_lan_minimal"
snap="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr_snap[@]}" "${snap_url}"
)"
OUT="${snap}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert isinstance(j, dict) and j.get("status") == "ok", "snapshot status=ok attendu"
lyra = j.get("lyra")
assert isinstance(lyra, dict), "lyra attendu dict"
meta = lyra.get("meta")
assert isinstance(meta, dict), "lyra.meta attendu dict"
print("OK: snapshot")
PY

echo ""
echo "== 5) backend internal/route (intent devops_probe, dry-run) =="
# devops_action force l’intent devops_probe côté orchestrator (pas de LLM).
# On reste en dry-run pour éviter toute approbation/tokens d’exécution réelle.
internal_url="http://${CORE}:${BACKEND_PORT}/v1/pilot/internal/route"
payload="$(
  python3 - <<'PY'
import json
print(json.dumps({
  "actor_id": "svc:smoke",
  "text": "probe",
  "context": {
    "devops_action": {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz", "max_bytes": 200},
    "devops_dry_run": True
  }
}))
PY
)"
resp="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" \
    -H "content-type: application/json" \
    -d "${payload}" \
    "${internal_url}"
)"
OUT="${resp}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, f"ok=true attendu, reçu: {j.get('ok')}"
res = j.get("result") or {}
assert isinstance(res, dict), "result dict attendu"
assert res.get("intent") == "devops_probe", f"intent devops_probe attendu, reçu: {res.get('intent')!r}"
print("OK: /v1/pilot/internal/route (devops_probe)")
PY

echo ""
echo "Smoke LAN minimal : OK"

