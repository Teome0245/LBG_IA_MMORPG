#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Smoke "phase 2" : commit idempotent (dialogue) vers mmmorpg_server (HTTP interne).
#
# Pré-requis :
# - sur 245 : HTTP interne actif (MMMORPG_INTERNAL_HTTP_HOST=0.0.0.0, MMMORPG_INTERNAL_HTTP_PORT=8773)
# - token optionnel : MMMORPG_INTERNAL_HTTP_TOKEN côté serveur, et LBG_MMMORPG_INTERNAL_HTTP_TOKEN côté client
#
# Usage:
#   bash infra/scripts/smoke_mmmorpg_commit.sh
#
# Variables :
#   LBG_LAN_HOST_MMO            défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT   défaut 8773
#   LBG_MMMORPG_INTERNAL_TOKEN  optionnel
#   LBG_SMOKE_NPC_ID            défaut npc:merchant
#

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"

if [[ -z "${TOKEN}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"
  if [[ -f "${SEC_FILE}" ]]; then
    TOKEN="$(
      python3 -c 'import os,re,sys; p=sys.argv[1]; t=""; 
import pathlib; s=pathlib.Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
for line in s:
  m=re.match(r"^\s*(MMMORPG_INTERNAL_HTTP_TOKEN|LBG_MMMORPG_INTERNAL_HTTP_TOKEN)\s*=\s*\"?(.*?)\"?\s*$", line)
  if m: t=m.group(2).strip(); break
print(t)' "${SEC_FILE}"
    )"
  fi
fi

hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

base="http://${MMO}:${PORT}"
trace_id="smoke_commit_$(date +%s)"

echo "== 1) Health =="
if ! curl -fsS "${hdr[@]}" "${base}/healthz" >/dev/null; then
  echo "ERREUR: healthz HTTP a échoué : ${base}/healthz" >&2
  echo "Debug:" >&2
  curl -isS "${hdr[@]}" "${base}/healthz" >&2 || true
  exit 1
fi
echo "OK: healthz"

echo ""
echo "== 2) Commit =="
if ! curl -fsS "${hdr[@]}" -H "content-type: application/json" \
  -X POST "${base}/internal/v1/npc/${NPC_ID}/dialogue-commit" \
  -d "{\"trace_id\":\"${trace_id}\",\"flags\":{\"quest_id\":\"q:smoke\",\"quest_accepted\":true}}" \
  >/dev/null; then
  echo "ERREUR: commit HTTP a échoué : ${base}/internal/v1/npc/${NPC_ID}/dialogue-commit" >&2
  echo "Debug:" >&2
  curl -isS "${hdr[@]}" -H "content-type: application/json" \
    -X POST "${base}/internal/v1/npc/${NPC_ID}/dialogue-commit" \
    -d "{\"trace_id\":\"${trace_id}\",\"flags\":{\"quest_id\":\"q:smoke\",\"quest_accepted\":true}}" \
    >&2 || true
  exit 1
fi
echo "OK: commit"

echo ""
echo "== 3) Snapshot (doit contenir world_flags.quest_id=q:smoke) =="
if ! snap="$(curl -fsS "${hdr[@]}" "${base}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}")"; then
  echo "ERREUR: snapshot HTTP a échoué. Vérifie que le PNJ existe (NPC_ID=${NPC_ID}) et que le token est correct." >&2
  echo "Hint: curl -v ${base}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}" >&2
  exit 1
fi
if [[ -z "${snap}" ]]; then
  echo "ERREUR: snapshot vide (réponse HTTP sans corps ?)" >&2
  echo "Debug (headers):" >&2
  curl -isS "${hdr[@]}" "${base}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=${trace_id}" >&2 || true
  exit 1
fi
echo "${snap}" | python3 -c 'import json,sys; j=json.load(sys.stdin); flags=(j["lyra"]["meta"].get("world_flags") or {}); assert flags.get("quest_id")=="q:smoke", flags; print("OK: snapshot flags")'

echo ""
echo "Smoke mmmorpg commit : OK"

