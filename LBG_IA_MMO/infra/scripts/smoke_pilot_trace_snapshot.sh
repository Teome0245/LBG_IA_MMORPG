#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — corrélation trace_id backend → snapshot WS interne
#
# 1) POST /v1/pilot/route (backend) => récupère trace_id
# 2) GET /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=<trace_id> (mmmorpg HTTP interne)
# 3) Vérifie que lyra.meta.trace_id == trace_id
#
# Usage:
#   bash infra/scripts/smoke_pilot_trace_snapshot.sh
#
# Variables :
#   LBG_LAN_HOST_CORE   défaut 192.168.0.140
#   LBG_LAN_HOST_MMO    défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (header X-LBG-Service-Token) ; sinon tente lecture infra/secrets/lbg.env
#   LBG_SMOKE_NPC_ID défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S défaut 60

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-60}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${TOKEN}" ]]; then
  SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"
  if [[ -f "${SEC_FILE}" ]]; then
    TOKEN="$(
      python3 -c 'import re,sys,pathlib; p=sys.argv[1]; t=""; 
s=pathlib.Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
for line in s:
  m=re.match(r"^\s*LBG_MMMORPG_INTERNAL_HTTP_TOKEN\s*=\s*\"?(.*?)\"?\s*$", line)
  if m: t=m.group(1).strip(); break
print(t)' "${SEC_FILE}"
    )"
  fi
fi

hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

echo "== 1) /v1/pilot/route (core=${CORE}) =="
pilot_out="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000/v1/pilot/route" \
    -H "content-type: application/json" \
    -d "{\"actor_id\":\"p:smoke\",\"text\":\"Bonjour\",\"context\":{\"world_npc_id\":\"${NPC_ID}\",\"history\":[]}}"
)"
echo "${pilot_out}"

trace_id="$(
  OUT="${pilot_out}" python3 - <<'PY'
import json, os
j = json.loads(os.environ.get("OUT","{}"))
assert j.get("ok") is True, "pilot ok attendu true"
tid = (j.get("trace_id") or "").strip()
print(tid)
PY
)"

if [[ -z "${trace_id}" ]]; then
  echo "ERREUR: trace_id vide dans la réponse pilot" >&2
  exit 1
fi

echo ""
echo "== 2) lyra-snapshot (mmo=${MMO}:${PORT}) trace_id=${trace_id} =="
snap_url="http://${MMO}:${PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}"
snap="$(curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" "${snap_url}")"
echo "${snap}"

OUT="${snap}" TRACE="${trace_id}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert isinstance(j, dict) and j.get("status") == "ok", "snapshot status=ok attendu"
lyra = j.get("lyra")
assert isinstance(lyra, dict), "lyra attendu dict"
meta = lyra.get("meta")
assert isinstance(meta, dict), "lyra.meta attendu dict"
tid = (meta.get("trace_id") or "").strip()
assert tid == os.environ["TRACE"], f"trace_id snapshot attendu {os.environ['TRACE']}, reçu {tid!r}"
print("OK: trace_id corrélé (pilot -> snapshot)")
PY

echo ""
echo "Smoke pilot trace_id -> snapshot : OK"

