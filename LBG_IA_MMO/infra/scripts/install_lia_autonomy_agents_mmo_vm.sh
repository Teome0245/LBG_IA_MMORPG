#!/usr/bin/env bash
# Installe le paquet agents/ sur la VM Prime (246) pour lbg-core3-ia-lia-autonomy.
# Usage : bash infra/scripts/install_lia_autonomy_agents_mmo_vm.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_VM_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"

echo "=== agents Lia → ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/agents ==="
ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${REMOTE_DIR}/agents/src/lbg_agents"
rsync -az --delete \
  "${ROOT_DIR}/agents/src/lbg_agents/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/agents/src/lbg_agents/"
scp "${ROOT_DIR}/agents/pyproject.toml" "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/agents/pyproject.toml"
scp "${ROOT_DIR}/infra/systemd/lbg-core3-ia-lia-autonomy.service" "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-ia-lia-autonomy.service"
scp "${ROOT_DIR}/tools/core3_ia_lia_autonomy_loop.py" "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/tools/core3_ia_lia_autonomy_loop.py"

ssh "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  cd \"${REMOTE_DIR}\"
  PY=\"/usr/bin/python3\"
  if [[ -x .venv/bin/python3 ]]; then
    .venv/bin/pip install -e agents/ -q
    PY=\".venv/bin/python3\"
  elif ! \"\${PY}\" -c \"import httpx\" 2>/dev/null; then
    sudo -n apt-get install -y -qq python3-httpx
  fi
  export PYTHONPATH=\"${REMOTE_DIR}/agents/src\"
  \"\${PY}\" -c \"import importlib.util; s=importlib.util.spec_from_file_location(\\\"lia_autonomy\\\",\\\"${REMOTE_DIR}/agents/src/lbg_agents/lia_autonomy.py\\\"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(\\\"agents ok\\\")\"
  sudo -n cp -f /tmp/lbg-core3-ia-lia-autonomy.service /etc/systemd/system/lbg-core3-ia-lia-autonomy.service
  sudo -n sed -i \"s|ExecStart=.*|ExecStart=/usr/bin/python3 ${REMOTE_DIR}/tools/core3_ia_lia_autonomy_loop.py|\" /etc/systemd/system/lbg-core3-ia-lia-autonomy.service
  sudo -n systemctl daemon-reload
  sudo -n systemctl enable --now lbg-core3-ia-lia-autonomy.service
  sleep 2
  systemctl is-active lbg-core3-ia-lia-autonomy.service
  journalctl -u lbg-core3-ia-lia-autonomy -n 3 --no-pager -q
'"
echo "OK"
