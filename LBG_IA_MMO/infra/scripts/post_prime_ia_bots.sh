#!/usr/bin/env bash
# Après démarrage / redémarrage de Prime : reconnecte Lia/Nix et placement cantina.
set -euo pipefail

BIN="${CORE3_BIN_DIR:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
LOG_TAG="post_prime_ia_bots"
ROOT="${LBG_IA_MMO_ROOT:-/opt/LBG_IA_MMO}"

log() { echo "${LOG_TAG}: $*"; }

wait_zone() {
  local i
  for i in $(seq 1 120); do
    if grep -q "started on port 44563" "${BIN}/log/core3.log" 2>/dev/null; then
      log "Zone Prime up (${i})"
      return 0
    fi
    sleep 5
  done
  log "WARN: timeout attente port 44563"
  return 1
}

log "attente Prime..."
wait_zone || true
sleep 15

log "reconnexion Lia/Nix (ensure_ia_bots_online)..."
export PYTHONPATH="${ROOT}/agents/src"
export LBG_CORE3_IA_SIDECAR_URL="${LBG_CORE3_IA_SIDECAR_URL:-http://127.0.0.1:8791}"
export LBG_CORE3_BOT_AUTO_CONNECT=1
if [[ -f /etc/lbg-ia-mmo.env ]]; then set -a; . /etc/lbg-ia-mmo.env; set +a; fi
if [[ -f /etc/lbg-core3-ia.env ]]; then set -a; . /etc/lbg-core3-ia.env; set +a; fi
/usr/bin/python3 - <<'PY' || true
from lbg_agents.core3_bot_connection import ensure_ia_bots_online
print(ensure_ia_bots_online())
PY

log "terminé"
