#!/usr/bin/env bash
# Déploie incarnation Lia + connexion orchestrateur → sidecar → core3client (VM 140 + 245).
#
# Usage :
#   bash infra/scripts/deploy_lia_orchestrator_incarnation.sh
#   bash infra/scripts/deploy_lia_orchestrator_incarnation.sh --connect-smoke
#   bash infra/scripts/deploy_lia_orchestrator_incarnation.sh --no-restart

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORE_HOST="${LBG_LAN_HOST_CORE:-192.168.0.140}"
MMO_HOST="${LBG_LAN_HOST_CORE3_PRIME:-${LBG_LAN_HOST_MMO:-192.168.0.246}}"
VM_USER="${LBG_VM_USER:-lbg}"
DO_RESTART=1
DO_CONNECT_SMOKE=0

for arg in "$@"; do
  case "$arg" in
    --no-restart) DO_RESTART=0 ;;
    --connect-smoke) DO_CONNECT_SMOKE=1 ;;
  esac
done

echo "=== Déploiement Lia orchestrateur → ${VM_USER}@${CORE_HOST} + ${VM_USER}@${MMO_HOST} ==="

STAGE="/tmp/lia_incarnation_deploy"
ssh "${VM_USER}@${CORE_HOST}" "mkdir -p ${STAGE}"
ssh "${VM_USER}@${MMO_HOST}" "mkdir -p ${STAGE}"

scp -q \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_orchestrator.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_connection.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_autonomy.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_perform.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_players.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_player_events.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_player_autonomy.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_bridge.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/dispatch.py" \
  "${ROOT_DIR}/content/core3/lia_perform_catalog.json" \
  "${ROOT_DIR}/content/core3/core3_ia_players.json" \
  "${ROOT_DIR}/orchestrator/router/routes/lia_incarnation.py" \
  "${ROOT_DIR}/orchestrator/router/routes/core3_player_routes.py" \
  "${ROOT_DIR}/orchestrator/router/routes/route_intent.py" \
  "${ROOT_DIR}/orchestrator/router/v1.py" \
  "${ROOT_DIR}/orchestrator/services/lia_autonomy.py" \
  "${ROOT_DIR}/orchestrator/shared_registry.py" \
  "${ROOT_DIR}/tools/core3_ia_sidecar/core3_ia_sidecar.py" \
  "${ROOT_DIR}/content/core3/lia_orchestrator_persona.json" \
  "${ROOT_DIR}/content/core3/lua/ia_bridge_screenplay.lua" \
  "${ROOT_DIR}/docs/core3_ia_phase_g_ai_players_population.md" \
  "${ROOT_DIR}/docs/core3_ia_phase_h_social_perception.md" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_player_vm.sh" \
  "${ROOT_DIR}/tools/core3_ia_player_autonomy_loop.py" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-player@.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-player-autonomy@.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-lia-autonomy.service" \
  "${VM_USER}@${CORE_HOST}:${STAGE}/"

scp -q \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_orchestrator.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_connection.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_autonomy.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/lia_perform.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_players.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_player_events.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_player_autonomy.py" \
  "${ROOT_DIR}/agents/src/lbg_agents/core3_bridge.py" \
  "${ROOT_DIR}/content/core3/lia_perform_catalog.json" \
  "${ROOT_DIR}/content/core3/core3_ia_players.json" \
  "${ROOT_DIR}/tools/core3_ia_sidecar/core3_ia_sidecar.py" \
  "${ROOT_DIR}/content/core3/lia_orchestrator_persona.json" \
  "${ROOT_DIR}/content/core3/lua/ia_bridge_screenplay.lua" \
  "${ROOT_DIR}/docs/core3_ia_phase_g_ai_players_population.md" \
  "${ROOT_DIR}/docs/core3_ia_phase_h_social_perception.md" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_player_vm.sh" \
  "${ROOT_DIR}/tools/core3_ia_player_autonomy_loop.py" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-player@.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-player-autonomy@.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-lia-autonomy.service" \
  "${VM_USER}@${MMO_HOST}:${STAGE}/"

install_core() {
  ssh "${VM_USER}@${CORE_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
S=/tmp/lia_incarnation_deploy
D=/opt/LBG_IA_MMO
sudo cp "$S/lia_orchestrator.py" "$S/lia_connection.py" "$S/lia_autonomy.py" "$S/lia_perform.py" "$S/core3_players.py" "$S/core3_player_events.py" "$S/core3_player_autonomy.py" "$S/core3_bridge.py" "$S/dispatch.py" \
  "$D/agents/src/lbg_agents/"
sudo mkdir -p "$D/content/core3"
sudo mkdir -p "$D/docs"
sudo cp "$S/lia_perform_catalog.json" "$S/lia_orchestrator_persona.json" "$S/core3_ia_players.json" "$D/content/core3/" 2>/dev/null || sudo cp "$S/lia_perform_catalog.json" "$S/core3_ia_players.json" "$D/content/core3/"
sudo cp "$S/core3_ia_phase_g_ai_players_population.md" "$S/core3_ia_phase_h_social_perception.md" "$D/docs/"
sudo cp "$S/lia_incarnation.py" "$D/orchestrator/router/routes/"
sudo cp "$S/core3_player_routes.py" "$D/orchestrator/router/routes/"
sudo cp "$S/route_intent.py" "$D/orchestrator/router/routes/"
sudo cp "$S/v1.py" "$D/orchestrator/router/"
sudo cp "$S/lia_autonomy.py" "$D/orchestrator/services/"
sudo cp "$S/shared_registry.py" "$D/orchestrator/"
sudo chown -R lbg:lbg "$D/agents/src/lbg_agents/lia_"* "$D/agents/src/lbg_agents/core3_players.py" "$D/agents/src/lbg_agents/core3_player_events.py" "$D/agents/src/lbg_agents/core3_player_autonomy.py" "$D/agents/src/lbg_agents/core3_bridge.py" "$D/agents/src/lbg_agents/dispatch.py" \
  "$D/content/core3/lia_perform_catalog.json" "$D/content/core3/core3_ia_players.json" \
  "$D/docs/core3_ia_phase_g_ai_players_population.md" "$D/docs/core3_ia_phase_h_social_perception.md" \
  "$D/orchestrator/router/routes/lia_incarnation.py" "$D/orchestrator/router/routes/core3_player_routes.py" "$D/orchestrator/router/routes/route_intent.py" "$D/orchestrator/router/v1.py" \
  "$D/orchestrator/services/lia_autonomy.py" "$D/orchestrator/shared_registry.py"
REMOTE
}

install_mmo() {
  ssh "${VM_USER}@${MMO_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
S=/tmp/lia_incarnation_deploy
D=/opt/LBG_IA_MMO
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin
sudo cp "$S/lia_orchestrator.py" "$S/lia_connection.py" "$S/lia_autonomy.py" "$S/lia_perform.py" "$S/core3_players.py" "$S/core3_player_events.py" "$S/core3_player_autonomy.py" "$S/core3_bridge.py" \
  "$D/agents/src/lbg_agents/"
sudo mkdir -p "$D/content/core3"
sudo mkdir -p "$D/docs"
sudo cp "$S/lia_perform_catalog.json" "$S/core3_ia_players.json" "$D/content/core3/"
sudo cp "$S/core3_ia_phase_g_ai_players_population.md" "$S/core3_ia_phase_h_social_perception.md" "$D/docs/"
sudo cp "$S/core3_ia_sidecar.py" "$D/tools/core3_ia_sidecar/"
sudo chmod +x "$D/tools/core3_ia_sidecar/core3_ia_sidecar.py"
sudo cp "$S/lia_orchestrator_persona.json" "$D/content/core3/"
sudo cp "$S/ia_bridge_screenplay.lua" "$BIN/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua"
sudo mkdir -p "$D/infra/scripts"
sudo cp "$S/run_core3_ia_bot_client_vm.sh" "$S/run_core3_ia_player_vm.sh" "$D/infra/scripts/"
sudo cp "$S/core3_ia_player_autonomy_loop.py" "$D/tools/"
sudo chmod +x "$D/infra/scripts/run_core3_ia_bot_client_vm.sh" "$D/infra/scripts/run_core3_ia_player_vm.sh" "$D/tools/core3_ia_player_autonomy_loop.py"
sudo cp "$S/lbg-core3-ia-player@.service" /etc/systemd/system/lbg-core3-ia-player@.service
sudo cp "$S/lbg-core3-ia-player-autonomy@.service" /etc/systemd/system/lbg-core3-ia-player-autonomy@.service
sudo cp "$S/lbg-core3-ia-lia-autonomy.service" /etc/systemd/system/lbg-core3-ia-lia-autonomy.service
sudo chown -R lbg:lbg "$D/agents/src/lbg_agents/lia_"* "$D/agents/src/lbg_agents/core3_players.py" "$D/agents/src/lbg_agents/core3_player_events.py" "$D/agents/src/lbg_agents/core3_player_autonomy.py" "$D/agents/src/lbg_agents/core3_bridge.py" \
  "$D/tools/core3_ia_sidecar/core3_ia_sidecar.py" "$D/content/core3/lia_orchestrator_persona.json" \
  "$D/content/core3/lia_perform_catalog.json" "$D/content/core3/core3_ia_players.json" \
  "$D/docs/core3_ia_phase_g_ai_players_population.md" "$D/docs/core3_ia_phase_h_social_perception.md" \
  "$D/infra/scripts/run_core3_ia_bot_client_vm.sh" "$D/infra/scripts/run_core3_ia_player_vm.sh" "$D/tools/core3_ia_player_autonomy_loop.py"
sudo chown lbg:lbg "$BIN/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua"
REMOTE
}

echo "--- Installation fichiers (core ${CORE_HOST}) ---"
install_core
echo "--- Installation fichiers (mmo ${MMO_HOST}) ---"
install_mmo

# --- Variables d'environnement ---
merge_env() {
  local host="$1"
  local sidecar_url="$2"
  ssh "${VM_USER}@${host}" "bash -s" <<REMOTE
set -euo pipefail
ENV=/etc/lbg-core3-ia.env
sudo touch "\${ENV}"
sudo chown root:root "\${ENV}"
sudo chmod 644 "\${ENV}"

upsert() {
  local key="\$1" val="\$2"
  if grep -q "^\${key}=" "\${ENV}" 2>/dev/null; then
    sudo sed -i "s|^\\\${key}=.*|\\\${key}=\\\${val}|" "\${ENV}"
  else
    echo "\${key}=\${val}" | sudo tee -a "\${ENV}" >/dev/null
  fi
}

upsert LBG_CORE3_IA_SIDECAR_URL "${sidecar_url}"
upsert LBG_ORCHESTRATOR_URL "http://${CORE_HOST}:8010"
upsert LBG_CORE3_LIA_ACTOR_ID "orchestrator:lia"
upsert LBG_CORE3_LIA_AUTO_CONNECT "1"
upsert LBG_CORE3_LIA_CONNECT_WAIT_S "120"
upsert LBG_CORE3_LIA_CONNECT_MODE "systemd"
upsert LBG_CORE3_LIA_BOT_SYSTEMD_UNIT "lbg-core3-ia-bot-client.service"
upsert LBG_CORE3_LIA_AUTONOMY_INTERVAL_S "80"
upsert LBG_CORE3_PLAYER_AUTONOMY_MODE "orchestrator"
upsert LBG_CORE3_PLAYER_AUTONOMY_INTERVAL_S "80"
upsert CORE3_IA_BOT_CHARACTER "Lia"
upsert CORE3_IA_BOT_NAME "Bot_IA"
upsert CORE3_IA_ZONE "tatooine"
REMOTE
}

echo "--- Mise à jour /etc/lbg-core3-ia.env ---"
merge_env "${CORE_HOST}" "http://${MMO_HOST}:8791"
merge_env "${MMO_HOST}" "http://127.0.0.1:8791"

ssh "${VM_USER}@${CORE_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
ENV=/etc/lbg-core3-ia.env
upsert() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "${ENV}" 2>/dev/null; then
    sudo sed -i "s|^${key}=.*|${key}=${val}|" "${ENV}"
  else
    echo "${key}=${val}" | sudo tee -a "${ENV}" >/dev/null
  fi
}
upsert LBG_CORE3_LIA_AUTONOMY_ENABLED "1"
upsert LBG_CORE3_LIA_AUTONOMY_MODE "invoke"
upsert LBG_CORE3_LIA_AUTONOMY_INTERVAL_S "80"
upsert LBG_CORE3_PLAYER_AUTONOMY_MODE "orchestrator"
upsert LBG_CORE3_PLAYER_AUTONOMY_INTERVAL_S "80"
REMOTE

if [[ "${DO_RESTART}" == "1" ]]; then
  echo "--- systemd (orchestrateur + sidecar LAN) ---"
  scp -q "${ROOT_DIR}/infra/systemd/lbg-orchestrator.service" "${VM_USER}@${CORE_HOST}:/tmp/"
  scp -q "${ROOT_DIR}/infra/systemd/lbg-core3-ia-sidecar.service" "${VM_USER}@${MMO_HOST}:/tmp/"
  ssh "${VM_USER}@${CORE_HOST}" "sudo cp /tmp/lbg-orchestrator.service /etc/systemd/system/ && sudo systemctl daemon-reload"
  ssh "${VM_USER}@${MMO_HOST}" "sudo cp /tmp/lbg-core3-ia-sidecar.service /etc/systemd/system/ && sudo systemctl daemon-reload"

  echo "--- Redémarrage services ---"
  ssh "${VM_USER}@${MMO_HOST}" "sudo systemctl restart lbg-core3-ia-sidecar.service; sleep 1; systemctl is-active lbg-core3-ia-sidecar.service"
  ssh "${VM_USER}@${CORE_HOST}" "sudo systemctl restart lbg-orchestrator.service; sleep 2; systemctl is-active lbg-orchestrator.service"
  ssh "${VM_USER}@${MMO_HOST}" "sudo systemctl enable lbg-core3-ia-bot-client.service 2>/dev/null || true
    sudo systemctl restart lbg-core3-ia-bot-client.service 2>/dev/null || sudo systemctl start lbg-core3-ia-bot-client.service
    sleep 1; systemctl is-active lbg-core3-ia-bot-client.service || true"
fi

echo ""
echo "--- Vérifications ---"
ssh "${VM_USER}@${CORE_HOST}" "curl -sf http://127.0.0.1:8010/healthz >/dev/null && echo orchestrator healthz OK"
ssh "${VM_USER}@${CORE_HOST}" "curl -s -o /dev/null -w 'lia/connect HTTP %{http_code}\n' -X POST http://127.0.0.1:8010/v1/lia/connect -H 'Content-Type: application/json' -d '{\"wait\":false}'"
ssh "${VM_USER}@${MMO_HOST}" "curl -s -o /dev/null -w 'sidecar lia/connect HTTP %{http_code}\n' -X POST http://127.0.0.1:8791/v1/lia/connect -H 'Content-Type: application/json' -d '{\"wait\":false}'"
ssh "${VM_USER}@${MMO_HOST}" "curl -s 'http://127.0.0.1:8791/v1/player-snapshot?player=Lia' | head -c 220; echo"

if [[ "${DO_CONNECT_SMOKE}" == "1" ]]; then
  echo ""
  echo "--- Smoke connexion (attente jusqu'à 120s) ---"
  ssh "${VM_USER}@${CORE_HOST}" "curl -sS -X POST http://127.0.0.1:8010/v1/lia/connect \
    -H 'Content-Type: application/json' \
    -d '{\"wait\":true,\"wait_s\":120}'"
  echo ""
fi

echo ""
echo "OK — doc : ${ROOT_DIR}/docs/core3_ia_lia_deploiement_mise_en_service.md"
