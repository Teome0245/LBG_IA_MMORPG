#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — auth sur POST /v1/pilot/reputation.
#
# Vérifie :
# - si `LBG_PILOT_INTERNAL_TOKEN` est défini : 401 sans token, 200 avec token
# - sinon : SKIP
#
# Usage:
#   bash infra/scripts/smoke_pilot_reputation_auth_lan.sh
#
# Variables :
#   LBG_LAN_HOST_CORE    défaut 192.168.0.140
#   LBG_BACKEND_PORT     défaut 8000
#   LBG_SMOKE_TIMEOUT_S  défaut 10
#   LBG_SMOKE_NPC_ID     défaut npc:merchant
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
PORT="${LBG_BACKEND_PORT:-8000}"
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

TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

url="http://${CORE}:${PORT}/v1/pilot/reputation"
payload="{\"npc_id\":\"${NPC_ID}\",\"delta\":1}"

curl_code() {
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" -o /dev/null -w "%{http_code}" "$@" || echo "000"
}

echo "=== Smoke LAN — auth pilot reputation ==="
echo "core=${CORE}:${PORT} timeout_s=${TIMEOUT_S} token_present=$([[ -n \"${TOKEN}\" ]] && echo 1 || echo 0)"

if [[ -z "${TOKEN}" ]]; then
  echo ""
  echo "== SKIP (LBG_PILOT_INTERNAL_TOKEN non défini) =="
  exit 0
fi

echo ""
echo "== 1) Sans token => 401 =="
code="$(curl_code -H "content-type: application/json" -d "${payload}" "${url}")"
if [[ "${code}" != "401" ]]; then
  echo "ERREUR: attendu 401, reçu ${code}" >&2
  echo "" >&2
  echo "Diagnostic :" >&2
  echo "- Si tu reçois 200, le gate n'est probablement PAS actif sur le backend ${CORE}." >&2
  echo "- Vérifie que la VM 140 a bien LBG_PILOT_INTERNAL_TOKEN dans son env (ex. /etc/lbg-ia-mmo.env) et que le service backend a été redémarré." >&2
  echo "- Commandes utiles (sur la VM 140) :" >&2
  echo "    sudo systemctl show -p Environment lbg-backend | tr ' ' '\\n' | grep LBG_PILOT_INTERNAL_TOKEN" >&2
  echo "    sudo systemctl restart lbg-backend" >&2
  echo "- Depuis le poste dev : pousser secrets puis redémarrer via tes scripts (push_secrets_vm.sh / deploy_vm.sh selon ton flow)." >&2
  exit 1
fi
echo "OK: 401"

echo ""
echo "== 2) Avec token => 200 =="
code="$(curl_code -H "content-type: application/json" -H "X-LBG-Service-Token: ${TOKEN}" -d "${payload}" "${url}")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: attendu 200, reçu ${code}" >&2
  exit 1
fi
echo "OK: 200"

echo ""
echo "Smoke auth pilot reputation : OK"

