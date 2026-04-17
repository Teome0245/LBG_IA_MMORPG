#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — reset seed + validation "nouveaux PNJ" (DESTRUCTIF sur l’état persisté).
#
# Fait :
# 1) stop/move/start `lbg-mmo-server` sur la VM MMO (reset état persisté, recharge du seed)
# 2) exécute `smoke_new_npcs_lan.sh`
#
# Usage :
#   bash infra/scripts/smoke_reset_seed_and_new_npcs_lan.sh
#
# Variables :
#   LBG_VM_HOST (défaut 192.168.0.245) / LBG_VM_USER (défaut lbg)
#   LBG_LAN_HOST_CORE / LBG_BACKEND_PORT / LBG_SMOKE_TIMEOUT_S
#   LBG_LAN_HOST_MMO / LBG_MMO_HTTP_PORT
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Smoke LAN — reset seed + nouveaux PNJ (DESTRUCTIF) ==="
echo "AVERTISSEMENT: ce script déplace l’état persisté du mmo_server sur la VM MMO."
echo ""

echo "== 1/2) Reset état mmo_server (VM MMO) =="
bash "${ROOT_DIR}/infra/scripts/reset_mmo_state_vm.sh"

echo ""
echo "Attente disponibilité mmo_server (healthz)…"
MMO_HOST="${LBG_LAN_HOST_MMO:-192.168.0.245}"
MMO_PORT="${LBG_MMO_HTTP_PORT:-8050}"
ok=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  code="$(
    curl -sS --connect-timeout 2 --max-time 3 -o /dev/null -w "%{http_code}" \
      "http://${MMO_HOST}:${MMO_PORT}/healthz" || echo "000"
  )"
  if [[ "${code}" == "200" ]]; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "${ok}" != "1" ]]; then
  echo "ERREUR: mmo_server pas prêt sur http://${MMO_HOST}:${MMO_PORT}/healthz" >&2
  exit 1
fi
echo "OK: mmo_server healthz=200"

echo ""
echo "== 2/2) Validation nouveaux PNJ =="
bash "${ROOT_DIR}/infra/scripts/smoke_new_npcs_lan.sh"

echo ""
echo "== 3/3) Commit E2E via backend (nouveaux PNJ) =="
bash "${ROOT_DIR}/infra/scripts/smoke_commit_dialogue_new_npcs_lan.sh"

echo ""
echo "Smoke reset seed + nouveaux PNJ : OK"

