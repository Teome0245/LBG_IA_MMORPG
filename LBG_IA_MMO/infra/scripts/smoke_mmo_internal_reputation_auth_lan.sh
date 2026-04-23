#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — auth sur POST mmo_server /internal/v1/npc/{npc_id}/reputation
#
# Vérifie :
# - si `LBG_MMO_INTERNAL_TOKEN` est défini : 401 sans token, 200 avec token
# - sinon : SKIP
#
# Variables :
#   LBG_LAN_HOST_MMO      défaut 192.168.0.245
#   LBG_MMO_HTTP_PORT     défaut 8050
#   LBG_SMOKE_TIMEOUT_S   défaut 10
#   LBG_SMOKE_NPC_ID      défaut npc:merchant
#

MMO_HOST="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMO_HTTP_PORT:-8050}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-10}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

TOKEN="${LBG_MMO_INTERNAL_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_MMO_INTERNAL_TOKEN")"
fi

url="http://${MMO_HOST}:${PORT}/internal/v1/npc/${NPC_ID}/reputation"
payload="{\"delta\":1}"

curl_code() {
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" -o /dev/null -w "%{http_code}" "$@" || echo "000"
}

echo "=== Smoke LAN — auth mmo_server internal reputation ==="
echo "mmo=${MMO_HOST}:${PORT} timeout_s=${TIMEOUT_S} token_present=$([[ -n \"${TOKEN}\" ]] && echo 1 || echo 0)"

if [[ -z "${TOKEN}" ]]; then
  echo ""
  echo "== SKIP (LBG_MMO_INTERNAL_TOKEN non défini) =="
  exit 0
fi

echo ""
echo "== 1) Sans token => 401 =="
code="$(curl_code -H "content-type: application/json" -d "${payload}" -X POST "${url}")"
if [[ "${code}" != "401" ]]; then
  echo "ERREUR: attendu 401, reçu ${code}" >&2
  echo "" >&2
  echo "Diagnostic :" >&2
  echo "- Si tu reçois 200, le gate n'est probablement PAS actif sur mmo_server (${MMO_HOST})." >&2
  echo "- Vérifie LBG_MMO_INTERNAL_TOKEN dans l'env du service lbg-mmo-server (VM 245) et redémarre." >&2
  exit 1
fi
echo "OK: 401"

echo ""
echo "== 2) Avec token => 200 =="
code="$(curl_code -H "content-type: application/json" -H "X-LBG-Service-Token: ${TOKEN}" -d "${payload}" -X POST "${url}")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: attendu 200, reçu ${code}" >&2
  exit 1
fi
echo "OK: 200"

echo ""
echo "Smoke auth mmo_server internal reputation : OK"

