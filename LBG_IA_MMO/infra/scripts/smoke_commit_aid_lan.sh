#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — commit aid_* via IA (orchestrator) sans LLM.
#
# 1) POST /v1/pilot/route avec context.world_action -> intent world_aid -> output.commit.flags aid_*
# 2) backend applique commit (mmmorpg_server) et expose commit_result
#
# Variables :
#   LBG_LAN_HOST_CORE      défaut 192.168.0.140
#   LBG_SMOKE_NPC_ID       défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S    défaut 30
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"

echo "=== Smoke LAN — commit aid (sans LLM) ==="
echo "core=${CORE}:8000 npc=${NPC_ID} timeout_s=${TIMEOUT_S}"
echo ""

out="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000/v1/pilot/route" \
    -H "content-type: application/json" \
    -d "{\"actor_id\":\"svc:smoke_aid_commit\",\"text\":\"aid\",\"context\":{\"world_npc_id\":\"${NPC_ID}\",\"world_action\":{\"kind\":\"aid\",\"hunger_delta\":-0.2,\"thirst_delta\":-0.1,\"fatigue_delta\":-0.2,\"reputation_delta\":5},\"history\":[]}}"
)"
echo "${out}" | head -c 1200
echo ""

OUT="${out}" python3 - <<'PY'
import json, os
j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, "ok=true attendu"
res = j.get("result") or {}
assert isinstance(res, dict)
assert res.get("intent") == "world_aid"
cr = j.get("commit_result") or {}
assert isinstance(cr, dict)
assert cr.get("ok") is True, f"commit_result.ok attendu true, reçu {cr.get('ok')}"
assert cr.get("accepted") is True, f"commit_result.accepted attendu true, reçu {cr.get('accepted')}"
print("OK: world_aid commit accepted")
PY

echo ""
echo "Smoke commit aid (LAN) : OK"

