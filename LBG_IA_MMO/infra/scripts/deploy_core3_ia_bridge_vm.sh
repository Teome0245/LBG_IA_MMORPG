#!/usr/bin/env bash
# Déploie le pont IA v0 (Lua + sidecar) sur Clean Antigravity (VM 245).
# Nécessite un rebuild Antigravity sur la VM après changement C++ (pollIaBridgeCommand).
#
# Usage :
#   bash infra/scripts/deploy_core3_ia_bridge_vm.sh
#   bash infra/scripts/deploy_core3_ia_bridge_vm.sh --build   # rsync + cmake build VM
#   bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart # redémarre core3-clean

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CLEAN_BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
REMOTE_TOOLS="/opt/LBG_IA_MMO/tools/core3_ia_sidecar"

DO_BUILD=0
DO_RESTART=0
for arg in "$@"; do
  case "$arg" in
    --build) DO_BUILD=1 ;;
    --restart) DO_RESTART=1 ;;
    --no-restart) DO_RESTART=0 ;;
  esac
done

IA_BRIDGE_LUA="${ROOT_DIR}/content/core3/lua/ia_bridge_screenplay.lua"
IA_SPAWN_TAG_LUA="${ROOT_DIR}/content/core3/lua/ia_spawn_tag.lua"
WE_LUA="${ROOT_DIR}/content/core3/lua/lbg_world_editor_screenplay.lua"
WE_HOOKS_LUA="${ROOT_DIR}/content/core3/lua/lbg_player_hooks.lua"
TERRAIN_LIB="${ROOT_DIR}/content/core3/lua/lbg_terrain_lib.lua"
LH_LUA="${ROOT_DIR}/content/core3/lua/lbg_lost_heaven_screenplay.lua"
WE_SCREENPLAYS="${ROOT_DIR}/content/core3/lua/screenplays.lua"
LOCAL_SCRIPTS="${LBG_NEW_MMO_REPO:-${ROOT_DIR}/../../new_mmo}/lbg-mmo/Core3/MMOCoreORB/bin/scripts"
if [[ ! -f "${IA_BRIDGE_LUA}" && ! -d "${LOCAL_SCRIPTS}/custom_scripts/screenplays" ]]; then
  echo "ERROR: ia_bridge_screenplay.lua introuvable (content/core3/lua ou new_mmo)" >&2
  exit 1
fi

echo "=== Pont IA (Phase C) → ${VM_USER}@${VM_HOST} (Prime / Tatooine) ==="

if [[ -f "${IA_BRIDGE_LUA}" ]]; then
  scp -q "${IA_BRIDGE_LUA}" \
    "${VM_USER}@${VM_HOST}:${CLEAN_BIN}/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua"
fi
if [[ -f "${IA_SPAWN_TAG_LUA}" ]]; then
  scp -q "${IA_SPAWN_TAG_LUA}" \
    "${VM_USER}@${VM_HOST}:${CLEAN_BIN}/scripts/custom_scripts/screenplays/ia_spawn_tag.lua"
fi
for lua in "${TERRAIN_LIB}" "${WE_LUA}" "${WE_HOOKS_LUA}" "${LH_LUA}"; do
  if [[ -f "${lua}" ]]; then
    scp -q "${lua}" \
      "${VM_USER}@${VM_HOST}:${CLEAN_BIN}/scripts/custom_scripts/screenplays/$(basename "${lua}")"
  fi
done
SCREENPLAYS_SRC=""
if [[ -f "${WE_SCREENPLAYS}" ]]; then
  SCREENPLAYS_SRC="${WE_SCREENPLAYS}"
elif [[ -f "${LOCAL_SCRIPTS}/custom_scripts/screenplays/screenplays.lua" ]]; then
  SCREENPLAYS_SRC="${LOCAL_SCRIPTS}/custom_scripts/screenplays/screenplays.lua"
fi
if [[ -n "${SCREENPLAYS_SRC}" ]]; then
  scp -q "${SCREENPLAYS_SRC}" \
    "${VM_USER}@${VM_HOST}:${CLEAN_BIN}/scripts/custom_scripts/screenplays/screenplays.lua"
fi
if [[ -d "${LOCAL_SCRIPTS}/custom_scripts/screenplays" && "${SCREENPLAYS_SRC}" != "${WE_SCREENPLAYS}" ]]; then
  :
fi

scp -q "${ROOT_DIR}/content/core3/core3_species_slot_map.json" \
  "${ROOT_DIR}/content/core3/core3_npc_pilots.json" \
  "${ROOT_DIR}/content/core3/core3_npc_pilot_bodies.json" \
  "${ROOT_DIR}/content/core3/core3_species_size_matrix.json" \
  "${ROOT_DIR}/content/core3/core3_npc_catalog.json" \
  "${ROOT_DIR}/content/core3/core3_quest_templates.json" \
  "${ROOT_DIR}/content/core3/core3_economy.json" \
  "${ROOT_DIR}/content/core3/core3_factions.json" \
  "${ROOT_DIR}/content/core3/core3_planet_rules.json" \
  "${ROOT_DIR}/content/core3/core3_npc_simulation.json" \
  "${VM_USER}@${VM_HOST}:/tmp/"

scp -q "${ROOT_DIR}/tools/core3_ia_sidecar/core3_ia_sidecar.py" \
  "${VM_USER}@${VM_HOST}:/tmp/core3_ia_sidecar.py"
scp -q "${ROOT_DIR}/infra/scripts/post_prime_ia_bots.sh" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${ROOT_DIR}/infra/scripts/lbg_world_export_agent.sh" \
  "${ROOT_DIR}/infra/scripts/apply_world_poi_sql_vm.sh" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime.service.d/ia-bots-reconnect.conf" \
  "${ROOT_DIR}/infra/systemd/lbg-world-export-agent.service" \
  "${ROOT_DIR}/infra/systemd/lbg-world-export-agent.timer" \
  "${ROOT_DIR}/infra/scripts/watch_core3_prime_login_health.sh" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-watchdog.service" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-prime-watchdog.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"
if [[ -d "${ROOT_DIR}/content/core3/world_poi" ]]; then
  scp -q -r "${ROOT_DIR}/content/core3/world_poi" \
    "${VM_USER}@${VM_HOST}:/tmp/lbg_world_poi"
fi
if [[ -d "${ROOT_DIR}/content/core3/locations" ]]; then
  scp -q -r "${ROOT_DIR}/content/core3/locations" \
    "${VM_USER}@${VM_HOST}:/tmp/lbg_locations"
fi
if [[ -f "${ROOT_DIR}/tools/world_editor/merge_export.py" ]]; then
  scp -q "${ROOT_DIR}/tools/world_editor/merge_export.py" \
    "${VM_USER}@${VM_HOST}:/tmp/merge_export.py"
fi
if [[ -f "${ROOT_DIR}/content/core3/ia_bridge/movement_mode" ]]; then
  scp -q "${ROOT_DIR}/content/core3/ia_bridge/movement_mode" \
    "${VM_USER}@${VM_HOST}:/tmp/ia_bridge_movement_mode"
fi

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p ${REMOTE_TOOLS} ${CLEAN_BIN}/ia_bridge ${CLEAN_BIN}/ia_bridge/world_poi /opt/LBG_IA_MMO/content/core3/world_poi /opt/LBG_IA_MMO/content/core3/locations /opt/LBG_IA_MMO/tools/world_editor
sudo cp /tmp/core3_ia_sidecar.py ${REMOTE_TOOLS}/core3_ia_sidecar.py
sudo chmod +x ${REMOTE_TOOLS}/core3_ia_sidecar.py
sudo cp /tmp/core3_species_slot_map.json /opt/LBG_IA_MMO/content/core3/core3_species_slot_map.json
sudo cp /tmp/core3_npc_pilots.json /opt/LBG_IA_MMO/content/core3/core3_npc_pilots.json
sudo cp /tmp/core3_npc_pilot_bodies.json /opt/LBG_IA_MMO/content/core3/core3_npc_pilot_bodies.json
sudo cp /tmp/core3_species_size_matrix.json /opt/LBG_IA_MMO/content/core3/core3_species_size_matrix.json
sudo cp /tmp/core3_npc_catalog.json /opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json
sudo cp /tmp/core3_quest_templates.json /opt/LBG_IA_MMO/content/core3/core3_quest_templates.json
sudo cp /tmp/core3_economy.json /opt/LBG_IA_MMO/content/core3/core3_economy.json
sudo cp /tmp/core3_factions.json /opt/LBG_IA_MMO/content/core3/core3_factions.json
sudo cp /tmp/core3_planet_rules.json /opt/LBG_IA_MMO/content/core3/core3_planet_rules.json
sudo cp /tmp/core3_npc_simulation.json /opt/LBG_IA_MMO/content/core3/core3_npc_simulation.json
sudo cp /tmp/core3_*.json ${CLEAN_BIN}/ia_bridge/ 2>/dev/null || true
sudo touch ${CLEAN_BIN}/ia_bridge/pending.jsonl
sudo touch ${CLEAN_BIN}/ia_bridge/player_snapshot.json
sudo touch ${CLEAN_BIN}/ia_bridge/npc_snapshots.json
sudo touch ${CLEAN_BIN}/ia_bridge/world_editor_session.json
sudo touch ${CLEAN_BIN}/ia_bridge/world_editor_export.queue
sudo touch ${CLEAN_BIN}/ia_bridge/world_editor_export.processed
sudo touch ${CLEAN_BIN}/ia_bridge/world_editor_audit.jsonl
# Cache admin compte → World Editor (perso Teome souvent à 0, compte SQL 4)
if command -v mysql >/dev/null 2>&1; then
  DB_USER="swgemu"
  DB_PASS="123456"
  DB_NAME="swgemu"
  CFG="${CLEAN_BIN}/conf/config-local.lua"
  if [[ -f "\$CFG" ]]; then
    DB_USER=\$(grep -E '^Core3\\.DBUser' "\$CFG" | sed 's/.*= *"\\(.*\\)".*/\\1/' | head -1)
    DB_PASS=\$(grep -E '^Core3\\.DBPass' "\$CFG" | sed 's/.*= *"\\(.*\\)".*/\\1/' | head -1)
    DB_NAME=\$(grep -E '^Core3\\.DBName' "\$CFG" | sed 's/.*= *"\\(.*\\)".*/\\1/' | head -1)
  fi
  mysql -u"\$DB_USER" -p"\$DB_PASS" "\$DB_NAME" -N -e \
    "SELECT CONCAT('account:', a.account_id, '=', a.admin_level) FROM accounts a WHERE a.admin_level >= 3;" 2>/dev/null | sudo tee ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json.tmp >/dev/null || true
  mysql -u"\$DB_USER" -p"\$DB_PASS" "\$DB_NAME" -N -e \
    "SELECT CONCAT('firstname:', LOWER(c.firstname), '=', a.admin_level) FROM characters c JOIN accounts a ON a.account_id=c.account_id WHERE a.admin_level >= 3;" 2>/dev/null | sudo tee -a ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json.tmp >/dev/null || true
  if [[ -s ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json.tmp ]]; then
    sudo mv ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json.tmp ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json
  else
    sudo rm -f ${CLEAN_BIN}/ia_bridge/lbg_account_admin.json.tmp
  fi
fi
if [[ -d /tmp/lbg_world_poi ]]; then
  sudo cp -a /tmp/lbg_world_poi/. /opt/LBG_IA_MMO/content/core3/world_poi/
  sudo cp -a /tmp/lbg_world_poi/. ${CLEAN_BIN}/ia_bridge/world_poi/ 2>/dev/null || true
fi
if [[ -d /tmp/lbg_locations ]]; then
  sudo cp -a /tmp/lbg_locations/. /opt/LBG_IA_MMO/content/core3/locations/
fi
if [[ -f /tmp/merge_export.py ]]; then
  sudo cp /tmp/merge_export.py /opt/LBG_IA_MMO/tools/world_editor/merge_export.py
  sudo chmod +x /opt/LBG_IA_MMO/tools/world_editor/merge_export.py
fi
sudo cp /tmp/lbg_world_export_agent.sh /opt/LBG_IA_MMO/infra/scripts/lbg_world_export_agent.sh
sudo cp /tmp/apply_world_poi_sql_vm.sh /opt/LBG_IA_MMO/infra/scripts/apply_world_poi_sql_vm.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/lbg_world_export_agent.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/apply_world_poi_sql_vm.sh
sudo cp /tmp/lbg-world-export-agent.service /etc/systemd/system/lbg-world-export-agent.service
sudo cp /tmp/lbg-world-export-agent.timer /etc/systemd/system/lbg-world-export-agent.timer
sudo cp /tmp/watch_core3_prime_login_health.sh /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_login_health.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_login_health.sh
sudo cp /tmp/lbg-core3-prime-watchdog.service /tmp/lbg-core3-prime-watchdog.timer /etc/systemd/system/
sudo mkdir -p /var/lib/lbg/core3_prime_watchdog
sudo chown ${VM_USER}:${VM_USER} /var/lib/lbg/core3_prime_watchdog
sudo systemctl daemon-reload
sudo systemctl enable lbg-world-export-agent.timer 2>/dev/null || true
sudo systemctl start lbg-world-export-agent.timer 2>/dev/null || true
sudo systemctl enable lbg-core3-prime-watchdog.timer 2>/dev/null || true
sudo systemctl restart lbg-core3-prime-watchdog.timer 2>/dev/null || true
if [[ -f /tmp/ia_bridge_movement_mode ]]; then
  sudo cp /tmp/ia_bridge_movement_mode ${CLEAN_BIN}/ia_bridge/movement_mode
fi
sudo touch ${CLEAN_BIN}/ia_bridge/bot_move.jsonl
sudo chown -R ${VM_USER}:${VM_USER} ${CLEAN_BIN}/ia_bridge ${REMOTE_TOOLS} /opt/LBG_IA_MMO/content/core3 /opt/LBG_IA_MMO/tools/world_editor
sudo mkdir -p /opt/LBG_IA_MMO/infra/scripts
sudo cp /tmp/post_prime_ia_bots.sh /opt/LBG_IA_MMO/infra/scripts/post_prime_ia_bots.sh
sudo cp /tmp/run_core3_ia_bot_client_vm.sh /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/post_prime_ia_bots.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo mkdir -p /etc/systemd/system/lbg-core3-prime.service.d
sudo cp /tmp/ia-bots-reconnect.conf /etc/systemd/system/lbg-core3-prime.service.d/ia-bots-reconnect.conf
sudo systemctl daemon-reload
ls -la ${CLEAN_BIN}/scripts/custom_scripts/screenplays/lbg_world_editor_screenplay.lua 2>/dev/null || true
ls -la ${CLEAN_BIN}/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua
ls -la ${REMOTE_TOOLS}/core3_ia_sidecar.py
EOF

if [[ "${DO_BUILD}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/build_core3_antigravity_vm.sh" --sync
  echo "Build lancé — après [100%] : bash infra/scripts/install_core3_clean_after_vm_build.sh"
fi

if [[ "${DO_RESTART}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/restart_core3_prime_vm.sh"
fi

echo ""
echo "Phase B : rebuild core3-clean requis si changement C++ (writeIaBridgePlayerSnapshot)"
echo "  bash infra/scripts/build_core3_antigravity_vm.sh --sync"
echo "  bash infra/scripts/install_core3_clean_after_vm_build.sh"
echo "Phase C : redémarrer core3-clean pour recharger le screenplay Lua (--restart)"
echo "Smoke B : bash infra/scripts/smoke_core3_ia_phase_b_lan.sh --with-think"
echo "Smoke C : bash infra/scripts/smoke_core3_ia_phase_c_lan.sh"
echo "Doc : ${ROOT_DIR}/docs/core3_ia_phase_c_npc_pilots.md"
