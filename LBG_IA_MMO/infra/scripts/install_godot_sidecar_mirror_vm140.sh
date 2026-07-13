#!/usr/bin/env bash
# Installe le service miroir sidecar → prime-client/cache sur VM core 140.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install miroir Godot sidecar → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-godot-sidecar-mirror.service" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo cp /tmp/lbg-godot-sidecar-mirror.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-godot-sidecar-mirror.service
sudo systemctl restart lbg-godot-sidecar-mirror.service
sleep 1
systemctl is-active lbg-godot-sidecar-mirror.service
EOF

echo "OK — cache rafraîchi toutes les 1s vers /opt/new_mmo/prime-client/cache"
