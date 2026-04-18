#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — LLM-on "ACTION_JSON" -> commit quest_* (via dialogue agent).
#
# Prérequis :
# - dialogue agent configuré LLM
# - LBG_DIALOGUE_WORLD_ACTIONS=1 sur la VM où tourne l'agent dialogue
#
# Ce smoke vérifie :
# - /v1/pilot/route (npc_dialogue) renvoie result.output.commit.flags quest_*
# - le backend applique commit_result.accepted=true (commit via HTTP interne mmmorpg_server)
#
# Variables :
#   LBG_LAN_HOST_CORE      défaut 192.168.0.140
#   LBG_SMOKE_NPC_ID       défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S    défaut 410
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-410}"

echo "=== Smoke LAN — dialogue LLM action -> commit quest ==="
echo "core=${CORE}:8000 path=/v1/pilot/route npc=${NPC_ID} timeout_s=${TIMEOUT_S}"
echo ""

payload="$(python3 - <<PY
import json
print(json.dumps({
  "actor_id": "p:smoke_llm_action_quest",
  "text": "Très bien, merci.",
  "context": {
    "npc_name": "Marchand",
    "world_npc_id": "${NPC_ID}",
    "_require_action_json": True,
    "quest_state": {"quest_id": "q:smoke_quest", "status": "open", "step": 0},
    "quest_hint": "Le joueur vient d'accepter une mission; il faut enregistrer l'état de quête côté monde (quest_id/step).",
    "_no_cache": True,
    "history": [],
  }
}, ensure_ascii=False))
PY
)"

attempt=0
while true; do
  attempt=$((attempt+1))
  echo "Attempt ${attempt}/3"
  out="$(
    curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
      "http://${CORE}:8000/v1/pilot/route" \
      -H "content-type: application/json" \
      -d "${payload}"
  )"
  echo "${out}" | head -c 2000
  echo ""

  if OUT="${out}" python3 - <<'PY'
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
assert flags.get("quest_id"), "flags.quest_id attendu"
assert "quest_step" in flags, "flags.quest_step attendu"
assert "quest_accepted" in flags, "flags.quest_accepted attendu"
cr = j.get("commit_result") or {}
assert isinstance(cr, dict)
assert cr.get("ok") is True and cr.get("accepted") is True, f"commit_result attendu ok+accepted, reçu {cr}"
print("OK: dialogue commit quest accepted")
PY
  then
    break
  fi
  if [ "${attempt}" -ge 3 ]; then
    echo "ERROR: échec après 3 tentatives" >&2
    exit 1
  fi
  sleep 1
done

echo ""
echo "Smoke dialogue LLM action quest commit (LAN) : OK"

