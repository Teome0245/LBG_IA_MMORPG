#!/usr/bin/env bash
# Vérification rapide des services monorepo (phase C — strangler).
# Usage : depuis LBG_IA_MMO/ avec venv optionnel :
#   source .venv/bin/activate
#   set -a && source infra/secrets/lbg.env 2>/dev/null || true; set +a
#   bash infra/scripts/verify_stack_local.sh
#
# Variables (défauts loopback) :
#   LBG_BACKEND_URL   défaut http://127.0.0.1:8000
#   LBG_ORCH_URL      défaut http://127.0.0.1:8010
#   LBG_MMO_HTTP_URL  défaut http://127.0.0.1:8050  (mmo_server)

set -euo pipefail

BACKEND="${LBG_BACKEND_URL:-http://127.0.0.1:8000}"
ORCH="${LBG_ORCH_URL:-http://127.0.0.1:8010}"
MMO="${LBG_MMO_HTTP_URL:-http://127.0.0.1:8050}"

fail=0
check() {
  local name="$1" url="$2"
  printf "  %-22s " "$name"
  if code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "$url" 2>/dev/null); then
    if [[ "$code" == "200" ]]; then
      echo "OK ($code)"
    else
      echo "HTTP $code — $url"
      fail=1
    fi
  else
    echo "indisponible — $url"
    fail=1
  fi
}

echo "=== Vérification stack locale (healthz) ==="
check "backend"   "${BACKEND%/}/healthz"
check "orchestrator" "${ORCH%/}/healthz"
check "mmo_server" "${MMO%/}/healthz"

if [[ "$fail" -ne 0 ]]; then
  echo ""
  echo "Au moins un service ne répond pas. Lancer les uvicorn (voir bootstrap.md) ou ajuster les URLs."
  exit 1
fi

echo ""
echo "Optionnel — Lyra monde (nécessite un PNJ dans le seed, ex. npc:smith) :"
if curl -s -f --connect-timeout 2 "${MMO%/}/v1/world/lyra?npc_id=npc:smith" | head -c 200; then
  echo ""
  echo "  GET /v1/world/lyra OK"
else
  echo "  (échec ou mmo_server sans ce PNJ — normal si seed différent)"
fi

echo ""
echo "OK — tous les healthz critiques sont joignables."
