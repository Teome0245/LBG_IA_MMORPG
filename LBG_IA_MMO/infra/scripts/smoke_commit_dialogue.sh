#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Smoke "phase 2 commit" :
# - appelle POST /v1/pilot/route (core 140)
# - vérifie commit_result
# - vérifie aussi que le snapshot HTTP interne `mmmorpg_server` expose `world_flags` (si accessible)
# - donne la commande de corrélation journald sur 245
#
# Usage:
#   bash infra/scripts/smoke_commit_dialogue.sh
#
# Variables:
#   LBG_LAN_HOST_CORE     défaut 192.168.0.140
#   LBG_LAN_HOST_MMO      défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (header X-LBG-Service-Token)
#   LBG_SMOKE_NPC_ID      défaut npc:merchant
#   LBG_SMOKE_TEXT        défaut "J'accepte la quête."
#   LBG_SMOKE_TIMEOUT_S   défaut 120

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TEXT="${LBG_SMOKE_TEXT:-J accepte la quête.}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-120}"

if [[ -z "${TOKEN}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"
  if [[ -f "${SEC_FILE}" ]]; then
    TOKEN="$(
      python3 -c 'import os,re,sys; p=sys.argv[1]; t=""; 
import pathlib; s=pathlib.Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
for line in s:
  m=re.match(r"^\s*LBG_MMMORPG_INTERNAL_HTTP_TOKEN\s*=\s*\"?(.*?)\"?\s*$", line)
  if m: t=m.group(1).strip(); break
print(t)' "${SEC_FILE}"
    )"
  fi
fi

echo "== Commit smoke (pilot/route) =="
echo "1) demander une quête (pour obtenir quest_id)…"
resp1="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000/v1/pilot/route" \
    -H "content-type: application/json" \
    -d "{\"actor_id\":\"p:smoke\",\"text\":\"Je cherche une quête.\",\"context\":{\"npc_name\":\"Marchand\",\"world_npc_id\":\"${NPC_ID}\",\"history\":[]}}"
)"
quest_id="$(
  printf "%s" "$resp1" | python3 -c 'import json,sys; j=json.load(sys.stdin); qid=(((j.get("result") or {}).get("output") or {}).get("quest_state") or {}).get("quest_id"); import sys as _s; _s.exit(2) if (not isinstance(qid,str) or not qid.strip()) else None; print(qid.strip())'
)" || true
if [[ -z "${quest_id}" ]]; then
  echo "ERREUR: quest_id introuvable dans la réponse (attendu via agent.quests)." >&2
  echo "$resp1" >&2
  exit 1
fi
echo "quest_id=${quest_id}"

echo "2) accepter (doit déclencher output.commit + commit_result)…"
resp2="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:8000/v1/pilot/route" \
    -H "content-type: application/json" \
    -d "{\"actor_id\":\"p:smoke\",\"text\":\"${TEXT}\",\"context\":{\"npc_name\":\"Marchand\",\"world_npc_id\":\"${NPC_ID}\",\"history\":[],\"quest_state\":{\"quest_id\":\"${quest_id}\",\"status\":\"open\",\"step\":0}}}"
)"

read -r trace_id accepted commit_ok <<EOF
$(printf "%s" "$resp2" | python3 -c 'import json,sys; j=json.load(sys.stdin); tid=j.get("trace_id") or ""; cr=j.get("commit_result") or {}; acc=cr.get("accepted"); ok=cr.get("ok"); print(tid, ("true" if acc is True else "false" if acc is False else ""), ("true" if ok is True else "false" if ok is False else ""))'
)
EOF

echo "trace_id=${trace_id}"
echo "commit_result_ok=${commit_ok:-} accepted=${accepted:-}"
echo ""
echo "3) vérifier snapshot (mmmorpg HTTP interne) : world_flags.quest_id = ${quest_id}"
hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi
snap_url="http://${MMO}:${PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}"
snap="$(curl -fsS --connect-timeout 3 --max-time "${TIMEOUT_S}" "${hdr[@]}" "${snap_url}")" || {
  echo "WARN: snapshot inaccessible (HTTP interne désactivé, token manquant, ou firewall). URL=${snap_url}" >&2
  snap=""
}
if [[ -n "${snap}" ]]; then
  printf "%s" "${snap}" | python3 -c 'import json,sys; j=json.load(sys.stdin); flags=((j.get("lyra") or {}).get("meta") or {}).get("world_flags") or {}; qid=flags.get("quest_id"); assert qid == "'"${quest_id}"'", (qid, flags); print("OK: snapshot world_flags.quest_id")'
fi
echo ""
echo "Astuce corrélation (sur 245):"
echo "  sudo journalctl -u lbg-mmmorpg-ws -n 200 --no-pager | grep \"dialogue_commit\" | grep \"${trace_id}\""
