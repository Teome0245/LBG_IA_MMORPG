#!/usr/bin/env bash
# Smoke Phase B — snapshot joueur Core3 IA (VM 245, sidecar :8791).
#
# Prérequis : Lia (Bot_IA) connectée en jeu sur Serveur Prime / Tatooine.
#
# Usage :
#   bash infra/scripts/smoke_core3_ia_phase_b_lan.sh
#   bash infra/scripts/smoke_core3_ia_phase_b_lan.sh --with-think   # appelle aussi /v1/think (LLM requis)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BOT_CHAR="${CORE3_IA_BOT_CHARACTER:-Lia}"
WITH_THINK=0

for arg in "$@"; do
  case "$arg" in
    --with-think) WITH_THINK=1 ;;
  esac
done

ssh_remote() {
  ssh -o ConnectTimeout=10 "${VM_USER}@${VM_HOST}" "$@"
}

echo "=== Smoke Core3 IA Phase B → ${VM_USER}@${VM_HOST} ==="

health="$(ssh_remote "curl -sf http://127.0.0.1:8791/healthz")"
echo "${health}" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('phase')=='B' or d.get('ok'); print('healthz OK', d.get('snapshot',''))"

snap_raw="$(ssh_remote "curl -s -w '\\n%{http_code}' 'http://127.0.0.1:8791/v1/player-snapshot?player=${BOT_CHAR}'")"
http_code="$(echo "${snap_raw}" | tail -n1)"
body="$(echo "${snap_raw}" | sed '$d')"

echo "snapshot HTTP ${http_code}"
echo "${body}" | python3 -m json.tool

if [[ "${http_code}" != "200" ]]; then
  echo "ERREUR: snapshot attendu HTTP 200 (joueur en ligne). Connectez ${BOT_CHAR} sur Prime/Tatooine." >&2
  exit 1
fi

echo "${body}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
s = d.get('snapshot', {})
assert s.get('online') is True, s
assert s.get('zone'), 'zone manquante'
print('OK online zone=', s.get('zone'), 'pos=', s.get('x'), s.get('y'), s.get('z'))
"

if [[ "${WITH_THINK}" == "1" ]]; then
  echo "--- /v1/think (LLM) ---"
  think="$(ssh_remote "curl -s -X POST http://127.0.0.1:8791/v1/think \
    -H 'Content-Type: application/json' \
    -d '{\"player\":\"${BOT_CHAR}\",\"prompt\":\"Dis où tu es en une phrase courte.\",\"enqueue\":true}'")"
  echo "${think}" | python3 -m json.tool
  echo "${think}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ok'), d
assert d.get('observation'), 'observation manquante'
print('think OK action=', d.get('action'))
"
  echo "Vérifiez en jeu un message [IA] sous ~4 s."
fi

echo "=== Smoke Phase B terminé ==="
