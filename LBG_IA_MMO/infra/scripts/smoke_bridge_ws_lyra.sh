#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Smoke "pont lecture seule" : mmmorpg_server (245) -> snapshot HTTP interne -> backend (140)
#
# Pré-requis :
# - sur 245 : MMMORPG_INTERNAL_HTTP_HOST=0.0.0.0, MMMORPG_INTERNAL_HTTP_PORT=8773, token optionnel, service lbg-mmmorpg-ws restart
# - sur 140 : LBG_MMMORPG_INTERNAL_HTTP_URL=http://192.168.0.245:8773 (+ token), backend restart
#
# Usage:
#   bash infra/scripts/smoke_bridge_ws_lyra.sh
#
# Variables :
#   LBG_LAN_HOST_CORE   défaut 192.168.0.140
#   LBG_LAN_HOST_MMO    défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT défaut 8773
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (header X-LBG-Service-Token)
#   LBG_SMOKE_NPC_ID défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S défaut 30

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"

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

hdr=()
if [[ -n "${TOKEN}" ]]; then
  hdr=(-H "X-LBG-Service-Token: ${TOKEN}")
fi

curl_json_or_die() {
  local url="$1"
  local label="$2"
  local headers_file body_file
  headers_file="$(mktemp)"
  body_file="$(mktemp)"
  if ! curl -sS "${hdr[@]}" --connect-timeout 3 --max-time "${TIMEOUT_S}" -D "${headers_file}" -o "${body_file}" "${url}"; then
    echo "ERREUR: ${label} — curl a échoué (réseau/timeout) : ${url}" >&2
    rm -f "${headers_file}" "${body_file}"
    exit 1
  fi
  local code
  code="$(head -n 1 "${headers_file}" | awk '{print $2}')"
  if [[ "${code}" != "200" ]]; then
    echo "ERREUR: ${label} — HTTP ${code} : ${url}" >&2
    echo "En-têtes:" >&2
    sed -n '1,20p' "${headers_file}" >&2
    echo "Corps (début):" >&2
    sed -n '1,5p' "${body_file}" >&2
    if [[ "${code}" == "401" && -z "${TOKEN}" ]]; then
      echo "" >&2
      echo "Hint: définis le token, ex.  LBG_MMMORPG_INTERNAL_HTTP_TOKEN=... bash infra/scripts/smoke_bridge_ws_lyra.sh" >&2
    fi
    rm -f "${headers_file}" "${body_file}"
    exit 1
  fi
  rm -f "${headers_file}" "${body_file}"
}

echo "== 1) Snapshot HTTP (mmmorpg interne) =="
curl_json_or_die "http://${MMO}:${PORT}/healthz" "healthz snapshot"
curl_json_or_die "http://${MMO}:${PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_ws_1" "lyra-snapshot"
echo "OK: snapshot"

echo ""
echo "Smoke bridge WS->Lyra : OK"

