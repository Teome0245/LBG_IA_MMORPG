#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — "quick" (évite la redondance, affiche des timings).
#
# Enchaîne (par défaut) :
# - smoke_vm_lan.sh (SSH + systemd + Ollama optionnel)
# - smoke_lan_minimal.sh (non destructif, sans LLM)
#
# Options (activation explicite) :
# - smoke_lan_core_desktop.sh si LBG_SMOKE_WITH_CORE_DESKTOP=1 (cœur + pilot/status, sans :8773 ; ne remplace pas minimal)
# - smoke_lan_pilot_agent_proxies.sh si LBG_SMOKE_WITH_AGENT_PROXIES=1 (GET healthz agents via backend)
# - smoke_pilot_route_lyra_meta_lan.sh (appelle /v1/pilot/route, peut toucher au LLM selon routing)
# - smoke_ws_ia_final_only_json.sh (WS→IA final-only, dépend du LLM)
#
# Usage:
#   bash infra/scripts/smoke_lan_quick.sh
#
# Variables :
#   LBG_SMOKE_TIMEOUT_S    défaut 30 (fallback global)
#   LBG_SMOKE_TIMEOUT_S_MINIMAL défaut 30 (smoke_lan_minimal)
#   LBG_SMOKE_TIMEOUT_S_PILOT   défaut 120 (pilot route)
#   LBG_SMOKE_TIMEOUT_S_WS      défaut 180 (WS→IA)
#   LBG_SMOKE_REPEAT       défaut 3  (pour WS→IA si activé)
#   LBG_SMOKE_WITH_REP=1   active le smoke réputation (sans LLM)
#   LBG_SMOKE_REP_DELTA    défaut 11 (si WITH_REP=1)
#   LBG_SMOKE_WITH_REP_WORLD=1 active le smoke "fallback monde" (sans LLM)
#   LBG_SMOKE_RESET_REP=1  remet la réputation à 0 avant les smokes rep (best-effort)
#   LBG_SMOKE_WITH_MMO_AUTH=1 active le smoke auth mmo_server internal (optionnel)
#   LBG_SMOKE_WITH_PILOT=1 active le smoke pilot route Lyra meta
#   LBG_SMOKE_WITH_WS=1    active le smoke WS→IA final-only JSON
#   LBG_SMOKE_WITH_GAMEPLAY_V1=1 active la recette MMO v1 gameplay jalon #1 (sans LLM, core HTTP)
#   LBG_SMOKE_WITH_GAMEPLAY_V2=1 active le jalon #2 (WS move+world_commit → snapshot :8773)
#   LBG_SMOKE_WITH_DEVOPS_SYSTEMD=1 active smoke_devops_systemd_lan.sh (dry-run par défaut ; allowlist sur core)
#   LBG_SMOKE_WITH_DEVOPS_SELFCHECK=1 active smoke_devops_selfcheck_lan.sh (bundle diagnostic ; dry-run par défaut)
#   LBG_SMOKE_WITH_CORE_DESKTOP=1 active smoke_lan_core_desktop.sh (cœur core + pilot/status ; sans :8773 MMO ; pas de POST route par défaut)
#   LBG_SMOKE_WITH_AGENT_PROXIES=1 active smoke_lan_pilot_agent_proxies.sh (GET healthz dialogue/desktop/pm via backend)
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
TIMEOUT_MINIMAL="${LBG_SMOKE_TIMEOUT_S_MINIMAL:-30}"
TIMEOUT_PILOT="${LBG_SMOKE_TIMEOUT_S_PILOT:-120}"
TIMEOUT_WS="${LBG_SMOKE_TIMEOUT_S_WS:-180}"
REPEAT="${LBG_SMOKE_REPEAT:-3}"
WITH_REP="${LBG_SMOKE_WITH_REP:-0}"
WITH_REP_WORLD="${LBG_SMOKE_WITH_REP_WORLD:-0}"
REP_DELTA="${LBG_SMOKE_REP_DELTA:-11}"
RESET_REP="${LBG_SMOKE_RESET_REP:-0}"
WITH_MMO_AUTH="${LBG_SMOKE_WITH_MMO_AUTH:-0}"
WITH_PILOT="${LBG_SMOKE_WITH_PILOT:-0}"
WITH_WS="${LBG_SMOKE_WITH_WS:-0}"
WITH_GAMEPLAY_V1="${LBG_SMOKE_WITH_GAMEPLAY_V1:-0}"
WITH_GAMEPLAY_V2="${LBG_SMOKE_WITH_GAMEPLAY_V2:-0}"
WITH_DEVOPS_SYSTEMD="${LBG_SMOKE_WITH_DEVOPS_SYSTEMD:-0}"
WITH_DEVOPS_SELFCHECK="${LBG_SMOKE_WITH_DEVOPS_SELFCHECK:-0}"
WITH_CORE_DESKTOP="${LBG_SMOKE_WITH_CORE_DESKTOP:-0}"
WITH_AGENT_PROXIES="${LBG_SMOKE_WITH_AGENT_PROXIES:-0}"

step() {
  local label="$1"
  shift
  echo ""
  echo "=== ${label} ==="
  local t0
  t0="$(date +%s)"
  "$@"
  local t1
  t1="$(date +%s)"
  echo "== OK: ${label} (elapsed_s=$((t1 - t0))) =="
}

echo "=== Smoke LAN quick ==="
echo "timeout_s=${TIMEOUT_S} minimal=${TIMEOUT_MINIMAL} pilot=${TIMEOUT_PILOT} ws=${TIMEOUT_WS} repeat=${REPEAT} with_rep=${WITH_REP} with_rep_world=${WITH_REP_WORLD} rep_delta=${REP_DELTA} reset_rep=${RESET_REP} with_mmo_auth=${WITH_MMO_AUTH} with_pilot=${WITH_PILOT} with_ws=${WITH_WS} with_gameplay_v1=${WITH_GAMEPLAY_V1} with_gameplay_v2=${WITH_GAMEPLAY_V2} with_devops_systemd=${WITH_DEVOPS_SYSTEMD} with_devops_selfcheck=${WITH_DEVOPS_SELFCHECK} with_core_desktop=${WITH_CORE_DESKTOP} with_agent_proxies=${WITH_AGENT_PROXIES}"

step "VM (SSH + systemd + Ollama)" \
  bash "${ROOT_DIR}/infra/scripts/smoke_vm_lan.sh"

step "LAN minimal (sans LLM)" \
  bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_lan_minimal.sh'"

if [[ "${WITH_REP}" == "1" ]]; then
  step "Réputation (sans LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' LBG_SMOKE_REP_DELTA='${REP_DELTA}' LBG_SMOKE_RESET_REP='${RESET_REP}' bash '${ROOT_DIR}/infra/scripts/smoke_reputation_lan.sh'"
fi

if [[ "${WITH_REP_WORLD}" == "1" ]]; then
  step "Réputation fallback monde (sans LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' LBG_SMOKE_REP_DELTA='${REP_DELTA}' LBG_SMOKE_RESET_REP='${RESET_REP}' bash '${ROOT_DIR}/infra/scripts/smoke_reputation_fallback_world_lan.sh'"
fi

if [[ "${WITH_MMO_AUTH}" == "1" ]]; then
  step "Auth mmo_server internal reputation (optionnel)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='10' bash '${ROOT_DIR}/infra/scripts/smoke_mmo_internal_reputation_auth_lan.sh'"
fi

if [[ "${WITH_PILOT}" == "1" ]]; then
  step "Pilot route Lyra meta (peut toucher LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_PILOT}' bash '${ROOT_DIR}/infra/scripts/smoke_pilot_route_lyra_meta_lan.sh'"
fi

if [[ "${WITH_WS}" == "1" ]]; then
  step "WS→IA final-only JSON (LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_WS}' LBG_SMOKE_REPEAT='${REPEAT}' bash '${ROOT_DIR}/infra/scripts/smoke_ws_ia_final_only_json.sh'"
fi

if [[ "${WITH_GAMEPLAY_V1}" == "1" ]]; then
  step "MMO v1 gameplay jalon #1 (sans LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_mmo_v1_gameplay_jalon1_lan.sh'"
fi

if [[ "${WITH_GAMEPLAY_V2}" == "1" ]]; then
  step "MMO v1 gameplay jalon #2 (WS→snapshot, sans LLM)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_ws_move_commit_snapshot_lan.sh'"
fi

if [[ "${WITH_DEVOPS_SYSTEMD}" == "1" ]]; then
  step "DevOps systemd_is_active (LAN, dry-run par défaut)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_devops_systemd_lan.sh'"
fi

if [[ "${WITH_DEVOPS_SELFCHECK}" == "1" ]]; then
  step "DevOps selfcheck bundle (LAN, dry-run par défaut)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_devops_selfcheck_lan.sh'"
fi

if [[ "${WITH_CORE_DESKTOP}" == "1" ]]; then
  step "Core + pilot desktop (sans mmmorpg :8773)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_lan_core_desktop.sh'"
fi

if [[ "${WITH_AGENT_PROXIES}" == "1" ]]; then
  step "Pilot agent proxies (GET healthz)" \
    bash -c "LBG_SMOKE_TIMEOUT_S='${TIMEOUT_MINIMAL}' bash '${ROOT_DIR}/infra/scripts/smoke_lan_pilot_agent_proxies.sh'"
fi

echo ""
echo "Smoke LAN quick : OK"

