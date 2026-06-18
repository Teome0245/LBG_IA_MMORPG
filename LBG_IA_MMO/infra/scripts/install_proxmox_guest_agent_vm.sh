#!/usr/bin/env bash
# Installe et active qemu-guest-agent (remontée IP / métriques vers Proxmox).
#
# Usage :
#   bash infra/scripts/install_proxmox_guest_agent_vm.sh 192.168.0.246
#   LBG_TARGET_VM_HOST=192.168.0.246 bash infra/scripts/install_proxmox_guest_agent_vm.sh

set -euo pipefail

VM_HOST="${1:-${LBG_TARGET_VM_HOST:-192.168.0.246}}"
VM_USER="${LBG_VM_USER:-lbg}"

echo "=== qemu-guest-agent sur ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
if ! command -v qemu-guest-agent >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq qemu-guest-agent
fi
sudo systemctl enable qemu-guest-agent.service
sudo systemctl restart qemu-guest-agent.service
systemctl is-active qemu-guest-agent.service
qemu-guest-agent --version 2>/dev/null || true
EOF

echo "OK — vérifier dans Proxmox : VM → Summary (IP, uptime, agent)"
