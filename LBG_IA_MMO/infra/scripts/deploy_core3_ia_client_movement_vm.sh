#!/usr/bin/env bash
# Déploie mouvement client IA : sources core3client + pont Lua + mode client + redémarrages.
#
# Usage (depuis LBG_IA_MMO/) :
#   bash infra/scripts/deploy_core3_ia_client_movement_vm.sh
#   bash infra/scripts/deploy_core3_ia_client_movement_vm.sh --local-binary   # copie binaire WSL si build local OK
#   bash infra/scripts/deploy_core3_ia_client_movement_vm.sh --movement-teleport  # garde teleport (pas client)
#
# Prérequis : SSH vers VM 245 (LBG_NEW_MMO_VM_HOST), core3-clean + services bot installés.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
CLEAN_MMOCORE="/opt/lbg-new-mmo-clean/MMOCoreORB"
CLEAN_BIN="${CLEAN_MMOCORE}/bin"
BUILD_DIR="${CLEAN_MMOCORE}/build"

USE_LOCAL_BINARY=0
MOVEMENT_MODE="client"
DO_RESTART=1

for arg in "$@"; do
  case "$arg" in
    --local-binary) USE_LOCAL_BINARY=1 ;;
    --movement-teleport) MOVEMENT_MODE="teleport" ;;
    --movement-walk) MOVEMENT_MODE="walk" ;;
    --no-restart) DO_RESTART=0 ;;
  esac
done

# Repo lbg-mmo (sources core3client)
NEW_MMO_REPO=""
for _cand in "${ROOT_DIR}/../../new_mmo" "${ROOT_DIR}/../new_mmo"; do
  if [[ -d "${_cand}/lbg-mmo/Core3/MMOCoreORB/src/client" ]]; then
    NEW_MMO_REPO="$(cd "${_cand}" && pwd)"
    break
  fi
done
if [[ -z "${NEW_MMO_REPO}" ]]; then
  echo "ERROR: lbg-mmo/Core3/MMOCoreORB/src/client introuvable" >&2
  exit 1
fi
CLIENT_SRC="${NEW_MMO_REPO}/lbg-mmo/Core3/MMOCoreORB/src/client"
LOCAL_CLIENT_BIN="${NEW_MMO_REPO}/lbg-mmo/Core3/MMOCoreORB/build/src/client/core3client"

echo "=== Déploiement mouvement client IA → ${VM_USER}@${VM_HOST} ==="
echo "    movement_mode=${MOVEMENT_MODE}"

# --- 1) core3client : binaire ou build sur VM ---
if [[ "${USE_LOCAL_BINARY}" == "1" ]]; then
  if [[ ! -x "${LOCAL_CLIENT_BIN}" ]]; then
    echo "Build local requis :" >&2
    echo "  cd ${NEW_MMO_REPO}/lbg-mmo/Core3/MMOCoreORB/build && cmake .. -DENABLE_BUILD_CLIENT=ON && cmake --build . --target core3client -j\$(nproc)" >&2
    exit 1
  fi
  echo ">>> Arrêt core3client (binaire en cours d'utilisation)"
  ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'STOP'
set -euo pipefail
for u in lbg-core3-ia-bot-client.service lbg-core3-ia-bot-client-nix.service lbg-core3-ia-player@nix.service; do
  sudo systemctl stop "$u" 2>/dev/null || true
done
pkill -x core3client 2>/dev/null || true
sleep 2
STOP
  echo ">>> Copie binaire local core3client"
  scp -q "${LOCAL_CLIENT_BIN}" "${VM_USER}@${VM_HOST}:/tmp/core3client"
  ssh "${VM_USER}@${VM_HOST}" "sudo cp /tmp/core3client ${CLEAN_BIN}/core3client && sudo chmod +x ${CLEAN_BIN}/core3client && ${CLEAN_BIN}/core3client --help | head -2"
else
  echo ">>> Sync sources client + build sur VM"
  ssh "${VM_USER}@${VM_HOST}" "mkdir -p /tmp/lbg-client-deploy/zone/packets"
  scp -q \
    "${CLIENT_SRC}/ClientCore.cpp" \
    "${CLIENT_SRC}/ClientCore.h" \
    "${VM_USER}@${VM_HOST}:/tmp/lbg-client-deploy/"
  scp -q \
    "${CLIENT_SRC}/zone/ZonePacketHandler.cpp" \
    "${CLIENT_SRC}/zone/PlayerLocomotion.cpp" \
    "${CLIENT_SRC}/zone/PlayerLocomotion.h" \
    "${CLIENT_SRC}/zone/BotMoveQueue.cpp" \
    "${CLIENT_SRC}/zone/BotMoveQueue.h" \
    "${VM_USER}@${VM_HOST}:/tmp/lbg-client-deploy/zone/"
  scp -q "${CLIENT_SRC}/zone/packets/ClientDataTransform.h" \
    "${VM_USER}@${VM_HOST}:/tmp/lbg-client-deploy/zone/packets/"

  ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
DEST="${CLEAN_MMOCORE}/src/client"
sudo cp /tmp/lbg-client-deploy/ClientCore.cpp /tmp/lbg-client-deploy/ClientCore.h "\${DEST}/"
sudo cp /tmp/lbg-client-deploy/zone/ZonePacketHandler.cpp "\${DEST}/zone/"
sudo cp /tmp/lbg-client-deploy/zone/PlayerLocomotion.cpp "\${DEST}/zone/"
sudo cp /tmp/lbg-client-deploy/zone/PlayerLocomotion.h "\${DEST}/zone/"
sudo cp /tmp/lbg-client-deploy/zone/BotMoveQueue.cpp "\${DEST}/zone/"
sudo cp /tmp/lbg-client-deploy/zone/BotMoveQueue.h "\${DEST}/zone/"
sudo mkdir -p "\${DEST}/zone/packets"
sudo cp /tmp/lbg-client-deploy/zone/packets/ClientDataTransform.h "\${DEST}/zone/packets/"
sudo chown -R ${VM_USER}:${VM_USER} "\${DEST}"

if [[ ! -d "${BUILD_DIR}" ]]; then
  echo "ERROR: ${BUILD_DIR} absent — configurer cmake sur la VM une fois" >&2
  exit 1
fi
for u in lbg-core3-ia-bot-client.service lbg-core3-ia-bot-client-nix.service lbg-core3-ia-player@nix.service; do
  sudo systemctl stop "\$u" 2>/dev/null || true
done
pkill -x core3client 2>/dev/null || true
sleep 2
echo "Reconfigure + build core3client sur VM..."
cmake -S "${CLEAN_MMOCORE}" -B "${BUILD_DIR}" -DENABLE_BUILD_CLIENT=ON >/dev/null
cmake --build "${BUILD_DIR}" --target core3client -j"\$(nproc)"
cp -f "${BUILD_DIR}/src/client/core3client" "${CLEAN_BIN}/core3client"
chmod +x "${CLEAN_BIN}/core3client"
"${CLEAN_BIN}/core3client" --help | head -2
EOF
fi

# --- 2) Pont Lua + JSON + sessions ---
echo ">>> Pont IA (Lua, sessions, movement_mode)"
bash "${ROOT_DIR}/infra/scripts/deploy_core3_ia_bridge_vm.sh" --no-restart

scp -q \
  "${ROOT_DIR}/content/core3/ia_bridge/lia_bot_session.json" \
  "${ROOT_DIR}/content/core3/ia_bridge/nix_bot_session.json" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p ${CLEAN_BIN}/ia_bridge
sudo cp /tmp/lia_bot_session.json ${CLEAN_BIN}/ia_bridge/lia_bot_session.json
sudo cp /tmp/nix_bot_session.json ${CLEAN_BIN}/ia_bridge/nix_bot_session.json
echo "${MOVEMENT_MODE}" | sudo tee ${CLEAN_BIN}/ia_bridge/movement_mode >/dev/null
sudo touch ${CLEAN_BIN}/ia_bridge/bot_move.jsonl
sudo chown -R ${VM_USER}:${VM_USER} ${CLEAN_BIN}/ia_bridge
echo "movement_mode=\$(cat ${CLEAN_BIN}/ia_bridge/movement_mode)"
ls -la ${CLEAN_BIN}/core3client ${CLEAN_BIN}/ia_bridge/movement_mode
EOF

# --- 3) Redémarrages ---
if [[ "${DO_RESTART}" == "1" ]]; then
  echo ">>> Redémarrage services"
  bash "${ROOT_DIR}/infra/scripts/restart_core3_prime_vm.sh" || true

  ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
restart_unit() {
  local u="$1"
  if systemctl list-unit-files "${u}" 2>/dev/null | grep -q "${u}"; then
    sudo systemctl restart "${u}" 2>/dev/null || true
    sleep 2
    systemctl is-active "${u}" 2>/dev/null || echo "WARN: ${u} inactif"
  fi
}
restart_unit lbg-core3-ia-sidecar.service
restart_unit lbg-core3-ia-bot-client.service
restart_unit lbg-core3-ia-bot-client-nix.service
restart_unit lbg-core3-ia-player@nix.service
EOF
fi

echo ""
echo "=== Terminé ==="
echo "Vérifier :"
echo "  ssh ${VM_USER}@${VM_HOST} 'cat ${CLEAN_BIN}/ia_bridge/movement_mode; pgrep -a core3client; tail -5 ${CLEAN_BIN}/log/core3client.log 2>/dev/null || true'"
echo "Test :"
echo "  ssh ${VM_USER}@${VM_HOST} \"echo 'move_to|Lia|3465|-4795|5|3' >> ${CLEAN_BIN}/ia_bridge/bot_move.jsonl\""
