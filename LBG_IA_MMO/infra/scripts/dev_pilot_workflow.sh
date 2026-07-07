#!/usr/bin/env bash
# Workflow pilot — aligné topologie prod LAN + WSL test en parallèle.
#
# PROD LAN (référence) :
#   110 — Front (Nginx :8080), UI pilot_shell, Ollama :11434
#   140 — Backend :8000, orchestrateur :8010, agents
#   245 — Core3 PreCU
#   246 — Core3 Prime (MMO personnalisé)
#
# WSL = environnement de TEST en parallèle (pas une copie complète de la prod).
#   - UI dev :5175 avec proxy Vite → prod LAN (voir pilot_shell/.env.development)
#   - apiBase vide dans Réglages → same-origin → 140 via proxy
#   - Déploiement UI prod → 110 (pas 140)
#
# Usage :
#   bash infra/scripts/dev_pilot_workflow.sh
#       → build UI + rsync → 110 + vérif LAN
#   bash infra/scripts/dev_pilot_workflow.sh --full
#       → deploy core@140 + front@110 + restart + build + rsync 110
#   bash infra/scripts/dev_pilot_workflow.sh --dev
#       → publish 110 + npm run dev (WSL test)
#   bash infra/scripts/dev_pilot_workflow.sh --full --dev
#   bash infra/scripts/dev_pilot_workflow.sh --dev-only
#   bash infra/scripts/dev_pilot_workflow.sh --verify-only
#
# Variables :
#   LBG_LAN_HOST_CORE   (défaut 192.168.0.140)
#   LBG_LAN_HOST_FRONT  (défaut 192.168.0.110)
#   LBG_VM_USER         (défaut lbg)
#   LBG_VM_DIR          (défaut /opt/LBG_IA_MMO)
#   LBG_DEV_PORT        (défaut 5175)
#   LBG_NGINX_PILOT_PORT (défaut 8080)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORE_HOST="${LBG_LAN_HOST_CORE:-192.168.0.140}"
FRONT_HOST="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
MMO_PRECU_HOST="${LBG_LAN_HOST_MMO:-192.168.0.245}"
MMO_PRIME_HOST="${LBG_LAN_HOST_PRIME:-192.168.0.246}"
VM_USER="${LBG_VM_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
DEV_PORT="${LBG_DEV_PORT:-5175}"
NGINX_PORT="${LBG_NGINX_PILOT_PORT:-8080}"

API_BASE="http://${CORE_HOST}:8000"
PM_BASE="http://${CORE_HOST}:8055"
FRONT_UI="http://${FRONT_HOST}:${NGINX_PORT}"
OLLAMA_BASE="http://${FRONT_HOST}:11434"

DO_FULL=0
DO_DEV=0
DO_DEV_ONLY=0
SKIP_BUILD=0
NO_RSYNC=0
VERIFY_ONLY=0

usage() {
  sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --full) DO_FULL=1 ;;
    --dev) DO_DEV=1 ;;
    --dev-only) DO_DEV_ONLY=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --no-rsync) NO_RSYNC=1 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Option inconnue : $arg (voir --help)" >&2
      exit 1
      ;;
  esac
done

SSH_OPTS=(
  -o ConnectTimeout=8
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
)

log() { echo "[dev_pilot_workflow] $*"; }

verify_lan() {
  log "Vérification prod LAN…"

  if curl -sf --max-time 5 "${API_BASE}/healthz" >/dev/null 2>&1; then
    log "  OK backend 140 ${API_BASE}/healthz"
  else
    log "  ÉCHEC backend 140 ${API_BASE}/healthz"
    return 1
  fi

  if curl -sf --max-time 5 "${PM_BASE}/healthz" >/dev/null 2>&1; then
    log "  OK agent PM 140 ${PM_BASE}/healthz"
  else
    log "  AVERTISSEMENT agent PM ${PM_BASE}/healthz"
  fi

  if curl -sf --max-time 8 -o /dev/null "${FRONT_UI}/" 2>/dev/null; then
    log "  OK front 110 ${FRONT_UI}/"
  else
    log "  AVERTISSEMENT front 110 ${FRONT_UI}/ (nginx / install_nginx_pilot_110 ?)"
  fi

  if curl -sf --max-time 5 "${OLLAMA_BASE}/" >/dev/null 2>&1; then
    log "  OK Ollama 110 ${OLLAMA_BASE}"
  else
    log "  INFO Ollama 110 non joint (optionnel si LLM ailleurs)"
  fi

  return 0
}

restart_core_services() {
  log "Restart services core @${CORE_HOST}…"
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${CORE_HOST}" bash -lc "
    set -euo pipefail
    sudo -n systemctl restart lbg-orchestrator lbg-backend lbg-agent-pm
    systemctl is-active lbg-orchestrator lbg-backend lbg-agent-pm
  "
}

run_full_deploy() {
  log "=== deploy core @${CORE_HOST} ==="
  LBG_DEPLOY_ROLE=core LBG_VM_HOST="${CORE_HOST}" LBG_VM_USER="${VM_USER}" \
    LBG_PILOT_WEB_ON_FRONT=1 \
    bash "${ROOT}/infra/scripts/deploy_vm.sh"
  restart_core_services

  log "=== deploy front @${FRONT_HOST} ==="
  LBG_DEPLOY_ROLE=front LBG_VM_HOST="${FRONT_HOST}" LBG_VM_USER="${VM_USER}" \
    bash "${ROOT}/infra/scripts/deploy_vm.sh"
}

build_ui() {
  if [[ "${SKIP_BUILD}" == "1" ]]; then
    log "Build UI ignoré (--skip-build)"
    return
  fi
  log "=== Build pilot_shell ==="
  bash "${ROOT}/infra/scripts/deploy_pilot_shell.sh"
}

rsync_ui_to_front() {
  if [[ "${NO_RSYNC}" == "1" ]]; then
    log "Rsync UI ignoré (--no-rsync)"
    return
  fi
  local src="${ROOT}/pilot_web/v2/"
  if [[ ! -f "${src}/index.html" ]]; then
    echo "[dev_pilot_workflow] ERREUR : ${src}index.html absent" >&2
    exit 1
  fi
  log "=== rsync pilot_web/v2 → ${FRONT_HOST} (UI prod) ==="
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${FRONT_HOST}" "mkdir -p '${REMOTE_DIR}/pilot_web/v2'"
  rsync -avz --delete \
    -e "ssh ${SSH_OPTS[*]}" \
    "${src}" \
    "${VM_USER}@${FRONT_HOST}:${REMOTE_DIR}/pilot_web/v2/"
}

start_wsl_dev() {
  log "=== WSL test — npm run dev :${DEV_PORT} ==="
  log "  Topologie : UI locale → proxy Vite → prod LAN"
  log "  UI       : http://127.0.0.1:${DEV_PORT}/pilot/v2/"
  log "  API      : ${API_BASE} (via proxy si apiBase vide)"
  log "  Front    : ${FRONT_UI} (prod)"
  log "  Core3    : PreCU ${MMO_PRECU_HOST} | Prime ${MMO_PRIME_HOST}"
  cd "${ROOT}/pilot_shell"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  export VITE_BACKEND_PROXY="${VITE_BACKEND_PROXY:-${API_BASE}}"
  export VITE_MMO_PROXY="${VITE_MMO_PROXY:-${FRONT_UI}}"
  exec npm run dev -- --host 0.0.0.0 --port "${DEV_PORT}"
}

print_summary() {
  echo ""
  log "Référence infra"
  echo "  110 Front+LLM : ${FRONT_UI}  (UI prod pilot_shell)"
  echo "  140 Backend   : ${API_BASE}"
  echo "  245 PreCU     : ${MMO_PRECU_HOST}"
  echo "  246 Prime     : ${MMO_PRIME_HOST}"
  echo ""
  log "WSL test"
  echo "  Dev UI        : http://127.0.0.1:${DEV_PORT}/pilot/v2/"
  echo "  Réglages      : apiBase VIDE (proxy → 140) ou ${API_BASE}"
  echo ""
  echo "  Complet       : bash infra/scripts/dev_pilot_workflow.sh --full --dev"
}

if [[ "${DO_DEV_ONLY}" == "1" ]]; then
  start_wsl_dev
fi

if [[ "${VERIFY_ONLY}" == "1" ]]; then
  verify_lan || exit 1
  print_summary
  exit 0
fi

if [[ "${DO_FULL}" == "1" ]]; then
  run_full_deploy
fi

build_ui
rsync_ui_to_front
verify_lan || true
print_summary

if [[ "${DO_DEV}" == "1" ]]; then
  start_wsl_dev
fi

log "Terminé."
