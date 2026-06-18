#!/usr/bin/env bash
# Serveur HTTP statique pour patches client SWG (launchpad :8080).
set -euo pipefail
VM_HOST="${VM_HOST:-192.168.0.245}"
VM_USER="${VM_USER:-lbg}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOTE_DIR="/home/lbg/lbg-client-patches"
PORT="${LBG_CLIENT_PATCH_PORT:-8080}"

ssh "${VM_USER}@${VM_HOST}" "mkdir -p ${REMOTE_DIR}"
rsync -avz --delete \
  "${ROOT_DIR}/infra/client-patch-server/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
mkdir -p ${REMOTE_DIR}
if ! command -v python3 >/dev/null; then
  echo "python3 requis" >&2
  exit 1
fi
# systemd unit
sudo tee /etc/systemd/system/lbg-client-patch.service >/dev/null <<UNIT
[Unit]
Description=LBG client patch server (static)
After=network.target

[Service]
Type=simple
User=${VM_USER}
WorkingDirectory=${REMOTE_DIR}
ExecStart=/usr/bin/python3 -m http.server ${PORT} --bind 0.0.0.0
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now lbg-client-patch.service
sleep 1
curl -sf "http://127.0.0.1:${PORT}/patches/prime/manifest.json" | head -c 120
echo ""
systemctl is-active lbg-client-patch.service
EOF

echo "Patch server : http://${VM_HOST}:${PORT}/patches/{precu,prime}/manifest.json"
