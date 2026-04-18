#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — WS hello → pont IA (LLM-on actions monde) → commit aid_* → snapshot
#
# Ce smoke fait :
# 1) Snapshot "avant" sur mmmorpg internal HTTP
# 2) WS connect + envoie un `hello` avec `world_npc_id`, `npc_name`, `text`
#    + `ia_context: {"_require_action_json": true}` (pour fiabiliser la génération ACTION_JSON)
# 3) Attend un `world_tick` contenant `npc_reply` + `trace_id`
# 4) Snapshot "après" avec ?trace_id=<trace> et vérifie que le placeholder a été remplacé.
#    (Si le LLM répond et commit, la réputation augmente généralement ; sinon fallback.)
#
# Variables:
#   LBG_LAN_HOST_MMO             défaut 192.168.0.245
#   LBG_MMMORPG_WS_PORT          défaut 7733
#   LBG_MMMORPG_INTERNAL_PORT    défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (sinon lu dans infra/secrets/lbg.env)
#   LBG_SMOKE_NPC_ID             défaut npc:merchant
#   LBG_SMOKE_NPC_NAME           défaut "Marchand"
#   LBG_SMOKE_TIMEOUT_S          défaut 180
#

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
WS_PORT="${LBG_MMMORPG_WS_PORT:-7733}"
HTTP_PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
NPC_NAME="${LBG_SMOKE_NPC_NAME:-Marchand}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-410}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${TOKEN}" ]]; then
  SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"
  if [[ -f "${SEC_FILE}" ]]; then
    TOKEN="$(
      python3 - <<'PY'
import pathlib, re
s = pathlib.Path("infra/secrets/lbg.env").read_text(encoding="utf-8", errors="ignore")
for key in ("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", "MMMORPG_INTERNAL_HTTP_TOKEN"):
    m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"?([^"\n]+)"?\s*$', s, re.M)
    if m:
        print(m.group(1).strip())
        raise SystemExit(0)
print("")
PY
    )"
  fi
fi

hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

echo "=== Smoke WS hello → IA → aid (LLM-on) ==="
echo "mmo=${MMO} ws=${WS_PORT} http=${HTTP_PORT} npc=${NPC_ID} timeout_s=${TIMEOUT_S}"

snap_before="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" \
    "http://${MMO}:${HTTP_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_before"
)"

echo ""
echo "Snapshot avant (tronc):"
echo "${snap_before}" | head -c 600
echo ""

if [[ "${snap_before}" == *"\"unauthorized\""* ]]; then
  echo "ERREUR: snapshot avant unauthorized — token manquant/invalide (header X-LBG-Service-Token)." >&2
  echo "Hint: export LBG_MMMORPG_INTERNAL_HTTP_TOKEN=... ou vérifie infra/secrets/lbg.env." >&2
  exit 1
fi

trace_and_reply="$(
  MMO="${MMO}" WS_PORT="${WS_PORT}" NPC_ID="${NPC_ID}" NPC_NAME="${NPC_NAME}" TIMEOUT_S="${TIMEOUT_S}" python3 - <<PY
import asyncio, json, os, sys, time
from websockets.asyncio.client import connect

mmo=os.environ.get("MMO")
ws_port=int(os.environ.get("WS_PORT"))
npc_id=os.environ.get("NPC_ID")
npc_name=os.environ.get("NPC_NAME")
timeout_s=float(os.environ.get("TIMEOUT_S"))

hello={
  "type":"hello",
  "player_name":"smoke",
  "world_npc_id": npc_id,
  "npc_name": npc_name,
  "text":"Je suis épuisé, j'ai faim et soif. Aide-moi tout de suite s'il te plaît, et ça me fera te faire davantage confiance.",
  "ia_context": {"_require_action_json": True},
}

async def main():
  uri=f"ws://{mmo}:{ws_port}"
  t0=time.time()
  async with connect(uri) as ws:
    await ws.send(json.dumps(hello, ensure_ascii=False))
    # recevoir welcome puis attendre world_tick avec npc_reply
    while True:
      if time.time()-t0 > timeout_s:
        raise RuntimeError("timeout: aucun world_tick npc_reply")
      raw=await asyncio.wait_for(ws.recv(), timeout=5.0)
      msg=json.loads(raw)
      if msg.get("type")=="world_tick" and isinstance(msg.get("npc_reply"), str) and msg["npc_reply"].strip():
        tid=str(msg.get("trace_id") or "").strip()
        rep=msg["npc_reply"].strip()
        # Le serveur peut envoyer un placeholder. On attend la réponse finale.
        if not tid or rep.startswith("…un instant."):
          continue
        print(json.dumps({"trace_id": tid, "npc_reply": rep}, ensure_ascii=False))
        return

asyncio.run(main())
PY
)"

echo ""
echo "WS result:"
echo "${trace_and_reply}"

trace_id="$(
  OUT="${trace_and_reply}" python3 - <<'PY'
import json, os
j=json.loads(os.environ["OUT"])
print((j.get("trace_id") or "").strip())
PY
)"

if [[ -z "${trace_id}" ]]; then
  echo "ERREUR: trace_id vide (WS)" >&2
  exit 1
fi

snap_after="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" \
    "http://${MMO}:${HTTP_PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}"
)"

echo ""
echo "Snapshot après (tronc):"
echo "${snap_after}" | head -c 600
echo ""

BEFORE="${snap_before}" AFTER="${snap_after}" TRACE="${trace_id}" python3 - <<'PY'
import json, os

before=json.loads(os.environ["BEFORE"])
after=json.loads(os.environ["AFTER"])
trace=os.environ["TRACE"]

def rep(j):
  ly=j.get("lyra") or {}
  meta=ly.get("meta") or {}
  r=(meta.get("reputation") or {}).get("value")
  return int(r)

assert before.get("status")=="ok"
assert after.get("status")=="ok"

lyra=after.get("lyra") or {}
meta=lyra.get("meta") or {}
assert (meta.get("trace_id") or "").strip()==trace, "trace_id snapshot non corrélé"

rb=rep(before)
ra=rep(after)
if ra > rb:
  print(f"OK: WS hello -> placeholder remplacé + rep a augmenté (rep {rb} -> {ra})")
else:
  print(f"OK: WS hello -> placeholder remplacé (rep inchangée {rb} -> {ra})")
PY

echo ""
echo "Smoke WS hello LLM aid : OK"

