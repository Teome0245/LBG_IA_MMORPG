#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — LLM-on "ACTION_JSON" -> commit aid_* (via dialogue agent).
#
# Prérequis :
# - dialogue agent configuré LLM (Ollama/OpenAI-like)
# - LBG_DIALOGUE_WORLD_ACTIONS=1 sur la VM où tourne l'agent dialogue (souvent core 140 ou LLM 110 selon topologie)
#
# Ce smoke vérifie uniquement que :
# - /v1/pilot/(internal/)route (npc_dialogue) renvoie result.output.commit.flags aid_*
# - le backend applique commit_result.accepted=true
#
# Variables :
#   LBG_LAN_HOST_CORE      défaut 192.168.0.140
#   LBG_SMOKE_NPC_ID       défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S    défaut 180
#   LBG_SMOKE_INTERNAL     défaut 0 (mettre 1 pour viser /v1/pilot/internal/route)
#   LBG_SMOKE_TOKEN        optionnel (requis si LBG_PILOT_INTERNAL_TOKEN est activé côté backend et LBG_SMOKE_INTERNAL=1)
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-180}"
USE_INTERNAL="${LBG_SMOKE_INTERNAL:-0}"
TOKEN="${LBG_SMOKE_TOKEN:-}"

PATH_ROUTE="/v1/pilot/route"
HDR_TOKEN=()
if [ "${USE_INTERNAL}" = "1" ]; then
  PATH_ROUTE="/v1/pilot/internal/route"
  if [ -n "${TOKEN}" ]; then
    HDR_TOKEN=(-H "X-LBG-Service-Token: ${TOKEN}")
  fi
fi

echo "=== Smoke LAN — dialogue LLM action -> commit aid ==="
echo "core=${CORE}:8000 path=${PATH_ROUTE} npc=${NPC_ID} timeout_s=${TIMEOUT_S}"
echo ""

payload="$(python3 - <<PY
import json
print(json.dumps({
  "actor_id": "p:smoke_llm_action",
  "text": "Aide-moi maintenant (action gameplay) : fais baisser faim/soif/fatigue et augmente un peu la réputation.",
  "context": {
    "npc_name": "Marchand",
    "world_npc_id": "${NPC_ID}",
    "_require_action_json": True,
    "history": [],
  }
}, ensure_ascii=False))
PY
)"

out="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000${PATH_ROUTE}" \
    -H "content-type: application/json" \
    "${HDR_TOKEN[@]}" \
    -d "${payload}"
)"
echo "${out}" | head -c 2000
echo ""

OUT="${out}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, "ok=true attendu"
res = j.get("result") or {}
assert isinstance(res, dict)
assert res.get("intent") == "npc_dialogue", f"intent npc_dialogue attendu, reçu {res.get('intent')!r}"
out = res.get("output") or {}
assert isinstance(out, dict)
commit = out.get("commit") or {}
assert isinstance(commit, dict), "output.commit attendu"
flags = commit.get("flags") or {}
assert isinstance(flags, dict), "commit.flags attendu dict"
assert "aid_hunger_delta" in flags or "aid_reputation_delta" in flags, "flags aid_* attendus"
cr = j.get("commit_result") or {}
assert isinstance(cr, dict)
assert cr.get("ok") is True and cr.get("accepted") is True, f"commit_result attendu ok+accepted, reçu {cr}"
print("OK: dialogue commit aid accepted")
PY

echo ""
echo "Smoke dialogue LLM action commit (LAN) : OK"

