#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — E2E réputation (sans LLM, fiable).
#
# Enchaîne :
# 1) (optionnel) vérifie le gate 401/200 sur POST /v1/pilot/reputation si token configuré
# 2) commit reputation_delta via backend (POST /v1/pilot/reputation)
# 3) vérifie la nouvelle valeur via snapshot interne mmmorpg_server
# 4) vérifie que le backend expose lyra_meta.reputation.value via POST /v1/pilot/internal/route (intent devops_probe)
#
# Usage:
#   bash infra/scripts/smoke_reputation_e2e_no_llm_lan.sh
#
# Variables :
#   LBG_SMOKE_TIMEOUT_S défaut 30
#   LBG_SMOKE_NPC_ID défaut npc:merchant
#   LBG_SMOKE_REP_DELTA défaut 11
#   LBG_SMOKE_RESET_REP défaut 0 ; si 1, remet la réputation à 0 avant le test (best-effort)
#   LBG_LAN_HOST_CORE défaut 192.168.0.140
#   LBG_BACKEND_PORT défaut 8000
#   LBG_LAN_HOST_MMO défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT défaut 8773
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
DELTA="${LBG_SMOKE_REP_DELTA:-11}"
RESET_REP="${LBG_SMOKE_RESET_REP:-0}"

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"

echo "=== Smoke LAN — E2E réputation (sans LLM) ==="
echo "core=${CORE}:${BACKEND_PORT} npc=${NPC_ID} delta=${DELTA} timeout_s=${TIMEOUT_S} reset_rep=${RESET_REP}"
echo ""

echo "== 1/4) Gate auth (write) =="
LBG_SMOKE_TIMEOUT_S="${TIMEOUT_S}" LBG_SMOKE_NPC_ID="${NPC_ID}" \
  bash "${ROOT_DIR}/infra/scripts/smoke_pilot_reputation_auth_lan.sh" || true

echo ""
echo "== 2/4) Commit + snapshot interne (réputation) =="
LBG_SMOKE_TIMEOUT_S="${TIMEOUT_S}" LBG_SMOKE_NPC_ID="${NPC_ID}" LBG_SMOKE_REP_DELTA="${DELTA}" LBG_SMOKE_RESET_REP="${RESET_REP}" \
  bash "${ROOT_DIR}/infra/scripts/smoke_reputation_lan.sh"

echo ""
echo "== 3/4) Vérif backend /v1/pilot/internal/route (lyra_meta.reputation) =="

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

PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"
if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi
hdr=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

payload="$(
  python3 - <<'PY' "$NPC_ID"
import json, sys
npc_id = sys.argv[1]
print(json.dumps({
  "actor_id": "svc:smoke",
  "text": "probe",
  "context": {
    "world_npc_id": npc_id,
    "devops_action": {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz", "max_bytes": 200},
    "devops_dry_run": True,
    "history": [],
  }
}))
PY
)"

out="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr[@]}" \
    -H "content-type: application/json" \
    -d "${payload}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/internal/route"
)"

OUT="${out}" NPC_ID="${NPC_ID}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, f"ok=true attendu, reçu: {j.get('ok')}"
meta = j.get("lyra_meta")
assert isinstance(meta, dict), f"lyra_meta dict attendu, reçu: {type(meta).__name__}"
rep = meta.get("reputation")
assert isinstance(rep, dict), f"lyra_meta.reputation dict attendu, reçu: {type(rep).__name__}"
v = rep.get("value")
assert isinstance(v, int), f"reputation.value int attendu, reçu: {v!r}"
print(f"OK: backend lyra_meta.reputation.value={v}")
PY

echo ""
echo "== 4/4) OK =="
echo "Smoke E2E réputation (sans LLM) : OK"

