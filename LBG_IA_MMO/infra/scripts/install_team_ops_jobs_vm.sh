#!/usr/bin/env bash
# Installe les timers playbooks ops équipe (stockage + Ollama) sur VM core 140.
#
# Usage :
#   bash infra/scripts/install_team_ops_jobs_vm.sh
#   LBG_CORE_VM_HOST=192.168.0.140 bash infra/scripts/install_team_ops_jobs_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-team-ops-* → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-ops-storage-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-ops-storage-job.timer" \
  "${ROOT_DIR}/infra/systemd/lbg-team-ops-ollama-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-ops-ollama-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_ops_storage /var/lib/lbg/team_ops_ollama
sudo chown lbg:lbg /var/lib/lbg/team_ops_storage /var/lib/lbg/team_ops_ollama
for u in lbg-team-ops-storage-job lbg-team-ops-ollama-job; do
  sudo cp "/tmp/${u}.service" "/tmp/${u}.timer" /etc/systemd/system/
done
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-ops-storage-job.timer lbg-team-ops-ollama-job.timer
sudo systemctl start lbg-team-ops-storage-job.timer lbg-team-ops-ollama-job.timer
systemctl is-active lbg-team-ops-storage-job.timer lbg-team-ops-ollama-job.timer
systemctl list-timers 'lbg-team-ops-*' --no-pager
EOF

echo ""
echo "OK — tâches visibles sur http://192.168.0.110:8080/#/team"
echo "  actor: system:team_ops_storage | system:team_ops_ollama"
echo "Test manuel :"
echo "  ssh ${VM_USER}@${VM_HOST} 'sudo systemctl start lbg-team-ops-ollama-job.service && journalctl -u lbg-team-ops-ollama-job -n 20 --no-pager'"
