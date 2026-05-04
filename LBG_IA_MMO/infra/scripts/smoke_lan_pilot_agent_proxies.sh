#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — sondes Pilot vers agents (proxies backend, sans POST /route).
#
# GET same-origin (via backend) :
# - /v1/pilot/agent-dialogue/healthz
# - /v1/pilot/agent-desktop/healthz
# - /v1/pilot/agent-pm/healthz
#
# Par défaut : affiche les codes HTTP ; exit 0 même si un agent renvoie 502 (service non branché).
# LBG_SMOKE_AGENT_PROXIES_STRICT=1 : exit 1 si une sonde n’est pas HTTP 2xx.
#
# Usage :
#   bash infra/scripts/smoke_lan_pilot_agent_proxies.sh
#
# Variables (alignées smoke_lan_core_desktop) :
#   LBG_LAN_HOST_CORE     défaut 192.168.0.140
#   LBG_BACKEND_PORT      défaut 8000
#   LBG_SMOKE_TIMEOUT_S   défaut 30
#

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
STRICT="${LBG_SMOKE_AGENT_PROXIES_STRICT:-0}"

BASE="http://${CORE}:${BACKEND_PORT}"

curl_code() {
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" -o /dev/null -w "%{http_code}" "$@" || echo "000"
}

echo "=== Smoke LAN — pilot agent proxies (GET healthz) ==="
echo "backend=${BASE} strict=${STRICT}"
echo ""

fail=0
probe() {
  local path="$1"
  local code
  code="$(curl_code "${BASE}${path}")"
  echo "${path} → HTTP ${code}"
  if [[ "${STRICT}" == "1" ]]; then
    if [[ "${code}" -lt 200 || "${code}" -gt 299 ]]; then
      fail=1
    fi
  fi
}

probe "/v1/pilot/agent-dialogue/healthz"
probe "/v1/pilot/agent-desktop/healthz"
probe "/v1/pilot/agent-pm/healthz"

if [[ "${fail}" -ne 0 ]]; then
  echo "ERREUR: mode strict — une sonde hors 2xx" >&2
  exit 1
fi

echo ""
echo "=== Smoke pilot agent proxies : OK ==="
