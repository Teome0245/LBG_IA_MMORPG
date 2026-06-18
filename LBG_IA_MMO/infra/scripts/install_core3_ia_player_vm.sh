#!/usr/bin/env bash
# Phase G — installe un joueur IA déclaré dans content/core3/core3_ia_players.json (VM 245).
#
# Usage :
#   bash infra/scripts/install_core3_ia_player_vm.sh nix
#   bash infra/scripts/install_core3_ia_player_vm.sh nix --enable

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
PLAYER_ID="${1:?player id requis (ex. nix)}"
DO_ENABLE=0

shift || true
for arg in "$@"; do
  case "$arg" in
    --enable) DO_ENABLE=1 ;;
  esac
done

eval "$(
  PLAYER_ID="${PLAYER_ID}" ROOT_DIR="${ROOT_DIR}" python3 <<'PY'
import json
import os
import shlex
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
player_id = os.environ["PLAYER_ID"]
data = json.loads((root / "content/core3/core3_ia_players.json").read_text())
for row in data.get("players", []):
    if row.get("id") == player_id:
        print("FIRSTNAME=" + shlex.quote(str(row["firstname"])))
        print("SESSION_REL=" + shlex.quote(str(row["session_json"])))
        print("ENV_FILE=" + shlex.quote(str(row["env_file"])))
        print("UNIT=" + shlex.quote(str(row["systemd_unit"])))
        break
else:
    raise SystemExit(f"joueur IA inconnu: {player_id}")
PY
)"

SESSION_LOCAL="${ROOT_DIR}/content/core3/${SESSION_REL}"
if [[ ! -f "${SESSION_LOCAL}" ]]; then
  echo "ERROR: session introuvable: ${SESSION_LOCAL}" >&2
  exit 1
fi

TMP="/tmp/lbg_ai_player_${PLAYER_ID}"
echo "=== Phase G joueur IA ${PLAYER_ID} (${FIRSTNAME}) → ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" "rm -rf '${TMP}' && mkdir -p '${TMP}'"
scp -q \
  "${SESSION_LOCAL}" \
  "${ROOT_DIR}/content/core3/core3_ia_players.json" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${ROOT_DIR}/infra/scripts/run_core3_ia_player_vm.sh" \
  "${ROOT_DIR}/infra/systemd/lbg-core3-ia-player@.service" \
  "${VM_USER}@${VM_HOST}:${TMP}/"

if [[ -f "${ROOT_DIR}/infra/snippets/${ENV_FILE}.example" ]]; then
  scp -q "${ROOT_DIR}/infra/snippets/${ENV_FILE}.example" "${VM_USER}@${VM_HOST}:${TMP}/env.example"
fi

ssh "${VM_USER}@${VM_HOST}" "PLAYER_ID='${PLAYER_ID}' FIRSTNAME='${FIRSTNAME}' SESSION_REL='${SESSION_REL}' ENV_FILE='${ENV_FILE}' DO_ENABLE='${DO_ENABLE}' TMP='${TMP}' bash -s" <<'EOF'
set -euo pipefail
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin
D=/opt/LBG_IA_MMO

if [[ ! -x "${BIN}/core3client" ]]; then
  echo "ERROR: ${BIN}/core3client absent" >&2
  exit 1
fi

sudo mkdir -p "${BIN}/ia_bridge" "${D}/infra/scripts" "${D}/content/core3"
sudo cp "${TMP}/$(basename "${SESSION_REL}")" "${BIN}/${SESSION_REL}"
sudo cp "${TMP}/core3_ia_players.json" "${D}/content/core3/core3_ia_players.json"
sudo cp "${TMP}/run_core3_ia_bot_client_vm.sh" "${D}/infra/scripts/run_core3_ia_bot_client_vm.sh"
sudo cp "${TMP}/run_core3_ia_player_vm.sh" "${D}/infra/scripts/run_core3_ia_player_vm.sh"
sudo chmod +x "${D}/infra/scripts/run_core3_ia_bot_client_vm.sh" "${D}/infra/scripts/run_core3_ia_player_vm.sh"
sudo cp "${TMP}/lbg-core3-ia-player@.service" /etc/systemd/system/lbg-core3-ia-player@.service
sudo chown -R lbg:lbg "${BIN}/${SESSION_REL}" "${D}/content/core3/core3_ia_players.json" "${D}/infra/scripts/run_core3_ia_"*.sh

if [[ ! -f "${BIN}/${ENV_FILE}" ]]; then
  if [[ -f "${TMP}/env.example" ]]; then
    sudo cp "${TMP}/env.example" "${BIN}/${ENV_FILE}"
  else
    sudo tee "${BIN}/${ENV_FILE}" >/dev/null <<ENV
CORE3_CLIENT_USERNAME=CHANGE_ME
CORE3_CLIENT_PASSWORD=CHANGE_ME
CORE3_CLIENT_LOGINHOST=192.168.0.245
CORE3_CLIENT_LOGINPORT=44553
ENV
  fi
  sudo chown lbg:lbg "${BIN}/${ENV_FILE}"
  sudo chmod 600 "${BIN}/${ENV_FILE}"
  echo "Cree ${BIN}/${ENV_FILE} — renseigner le mot de passe avant activation."
fi

sudo systemctl daemon-reload

if [[ "${DO_ENABLE}" == "1" ]]; then
  if grep -q 'CHANGE_ME' "${BIN}/${ENV_FILE}"; then
    echo "ERROR: ${BIN}/${ENV_FILE} contient encore CHANGE_ME" >&2
    exit 2
  fi
  sudo systemctl enable --now "lbg-core3-ia-player@${PLAYER_ID}.service"
else
  echo "Installer OK. Activation: sudo systemctl enable --now lbg-core3-ia-player@${PLAYER_ID}.service"
fi
EOF
