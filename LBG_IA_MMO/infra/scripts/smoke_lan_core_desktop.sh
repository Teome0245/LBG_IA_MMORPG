#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — cœur plateforme + Pilot desktop (sans VM mmmorpg / sans WS MMO).
#
# Couvre :
# - healthz backend + orchestrator
# - GET /v1/pilot/status (JSON pilot)
# - optionnel : POST /v1/pilot/route avec open_url + desktop_dry_run (vérifie la chaîne pilot → orchestrateur → agent.desktop en dry-run si configuré)
#
# Usage:
#   bash infra/scripts/smoke_lan_core_desktop.sh
#   (depuis la racine du workspace parent : même commande via le wrapper infra/scripts/ à cette racine)
#
# Variables :
#   LBG_LAN_HOST_CORE              défaut 192.168.0.140
#   LBG_BACKEND_PORT               défaut 8000
#   LBG_ORCHESTRATOR_PORT          défaut 8010
#   LBG_SMOKE_TIMEOUT_S            défaut 30
#   LBG_PILOT_INTERNAL_TOKEN       optionnel (header X-LBG-Service-Token si le backend l’exige)
#   LBG_SMOKE_DESKTOP_ROUTE        si 1 / true / on : étape POST /v1/pilot/route (défaut off) ; ou flag --desktop-route
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
ORCH_PORT="${LBG_ORCHESTRATOR_PORT:-8010}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"

DESKTOP_ROUTE_ARG=0
_remaining=()
for _a in "$@"; do
  if [[ "${_a}" == "--desktop-route" ]]; then
    DESKTOP_ROUTE_ARG=1
  else
    _remaining+=("${_a}")
  fi
done
set -- "${_remaining[@]}"

_raw="${LBG_SMOKE_DESKTOP_ROUTE:-}"
_raw="${_raw//$'\r'/}"
_raw="${_raw#"${_raw%%[![:space:]]*}"}"
_raw="${_raw%"${_raw##*[![:space:]]}"}"
DO_ROUTE=0
if [[ "${DESKTOP_ROUTE_ARG}" -eq 1 ]]; then
  DO_ROUTE=1
else
  case "${_raw}" in
    1|true|TRUE|yes|YES|on|ON) DO_ROUTE=1 ;;
  esac
fi

PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"

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
escaped = re.escape(key)
pat = re.compile(rf"^\s*{escaped}\s*=\s*\"?(.*?)\"?\s*$")
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    m = pat.match(line)
    if m:
        print(m.group(1).strip())
        raise SystemExit(0)
print("")
PY
}

if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

hdr_pilot=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_pilot=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

curl_code() {
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" -o /dev/null -w "%{http_code}" "$@" || echo "000"
}

echo "=== Smoke LAN — core + pilot desktop (sans mmmorpg MMO) ==="
echo "core=${CORE}:${BACKEND_PORT} orch=${CORE}:${ORCH_PORT} timeout_s=${TIMEOUT_S} desktop_route=${DO_ROUTE}"
echo ""

echo "== 1) healthz backend =="
code="$(curl_code "http://${CORE}:${BACKEND_PORT}/healthz")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: backend healthz HTTP ${code}" >&2
  exit 1
fi
echo "OK: backend healthz=200"

echo ""
echo "== 2) healthz orchestrator =="
code="$(curl_code "http://${CORE}:${ORCH_PORT}/healthz")"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: orchestrator healthz HTTP ${code}" >&2
  exit 1
fi
echo "OK: orchestrator healthz=200"

echo ""
echo "== 3) GET /v1/pilot/status =="
status_body="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/status"
)"
OUT="${status_body}" python3 - <<'PY'
import json, os
raw = os.environ["OUT"]
try:
    j = json.loads(raw)
except json.JSONDecodeError as e:
    raise SystemExit(f"ERREUR: réponse pilot/status n’est pas du JSON: {e}: {raw[:500]!r}")
if not isinstance(j, dict):
    raise SystemExit("ERREUR: pilot/status attendu objet JSON")
print("OK: pilot/status JSON objet")
PY

if [[ "${DO_ROUTE}" == "1" ]]; then
  echo ""
  echo "== 4) POST /v1/pilot/route (desktop open_url dry-run) =="
  route_body="$(
    curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
      "${hdr_pilot[@]}" \
      -H "content-type: application/json" \
      -d '{"actor_id":"smoke:desktop","text":"smoke open_url dry-run","context":{"desktop_dry_run":true,"desktop_action":{"kind":"open_url","url":"https://example.org"}}}' \
      -w "\n%{http_code}" \
      "http://${CORE}:${BACKEND_PORT}/v1/pilot/route"
  )"
  ROUTE="${route_body}" python3 - <<'PY'
import json, os
raw = os.environ["ROUTE"]
lines = raw.strip().split("\n")
if len(lines) < 2:
    raise SystemExit(f"ERREUR: réponse route inattendue: {raw[:800]!r}")
code_s = lines[-1].strip()
try:
    code = int(code_s)
except ValueError:
    raise SystemExit(f"ERREUR: code HTTP non entier: {code_s!r}")
body = "\n".join(lines[:-1])
if code != 200:
    raise SystemExit(f"ERREUR: POST /v1/pilot/route HTTP {code}: {body[:1500]}")
try:
    j = json.loads(body)
except json.JSONDecodeError as e:
    raise SystemExit(f"ERREUR: corps route JSON invalide: {e}")
if not isinstance(j, dict):
    raise SystemExit("ERREUR: route attendu objet JSON")
print("OK: route HTTP 200 + JSON")
PY
else
  echo ""
  echo "== 4) POST /v1/pilot/route — ignoré (pas d’étape route : export LBG_SMOKE_DESKTOP_ROUTE=1 ou $0 --desktop-route) =="
  echo "Exemples : LBG_SMOKE_DESKTOP_ROUTE=1 $(basename "$0")    ou    $(basename "$0") --desktop-route"
fi

echo ""
echo "=== Smoke core desktop : OK ==="
