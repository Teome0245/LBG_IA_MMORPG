#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — corrélation bout-en-bout :
# 1) WS → pont IA (ws_ia_cli final-only) => récupère trace_id
# 2) HTTP interne snapshot (lyra-snapshot?trace_id=...) avec le même trace_id
# 3) Vérifie que le snapshot renvoie lyra.meta.trace_id identique (corrélation logs).
#
# Usage:
#   bash infra/scripts/smoke_ws_ia_trace_snapshot.sh
#
# Variables :
#   LBG_LAN_HOST_MMO   défaut 192.168.0.245
#   LBG_LAN_HOST_CORE  défaut 192.168.0.140 (non requis ici, mais cohérent avec les autres smokes)
#   LBG_MMMORPG_WS_PORT défaut 7733
#   LBG_MMMORPG_INTERNAL_PORT défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (header X-LBG-Service-Token) ; sinon tente lecture infra/secrets/lbg.env
#   LBG_SMOKE_NPC_ID   défaut npc:merchant
#   LBG_SMOKE_NPC_NAME défaut "Marchand"
#   LBG_SMOKE_TEXT     défaut "Bonjour"
#   LBG_SMOKE_REPEAT   défaut 1
#   LBG_SMOKE_TIMEOUT_S défaut 120

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
WS_PORT="${LBG_MMMORPG_WS_PORT:-7733}"
HTTP_PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
NPC_NAME="${LBG_SMOKE_NPC_NAME:-Marchand}"
TEXT="${LBG_SMOKE_TEXT:-Bonjour}"
REPEAT="${LBG_SMOKE_REPEAT:-1}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${ROOT_DIR}/.venv/bin/python"
CLI="${ROOT_DIR}/mmmorpg_server/tools/ws_ia_cli.py"

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

echo "== 1) ws_ia_cli final-only (JSON) sur ws://${MMO}:${WS_PORT} =="
out="$(
  "${PY}" "${CLI}" \
    --ws "ws://${MMO}:${WS_PORT}" \
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

trace_id="$(
  OUT="${out}" python3 - <<'PY'
import json, os
j = json.loads(os.environ.get("OUT","{}"))
assert j.get("ok") is True, f"ok attendu true, reçu: {j.get('ok')}"
assert int(j.get("n_ok") or 0) >= 1, f"n_ok>=1 attendu, reçu: {j.get('n_ok')}"
tid = (j.get("trace_id") or "").strip()
print(tid)
PY
)"

if [[ -z "${trace_id}" ]]; then
  echo "ERREUR: trace_id vide dans la sortie ws_ia_cli" >&2
  exit 1
fi

echo ""
echo "== 2) Snapshot HTTP (mmmorpg interne) avec trace_id=${trace_id} =="
snap_url="http://${MMO}:${HTTP_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}"
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
print("OK: trace_id corrélé (snapshot)")
PY

echo ""
echo "Smoke ws_ia + snapshot corrélés : OK (core=${CORE}, mmo=${MMO})"

