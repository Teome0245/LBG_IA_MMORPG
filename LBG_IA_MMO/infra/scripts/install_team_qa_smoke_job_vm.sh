#!/usr/bin/env bash
# Installe le timer lbg-team-qa-smoke-job sur la VM core (140).
# Crée et exécute une tâche équipe ``qa`` (smoke_vm_lan.sh via LBG_TEAM_QA_SMOKE_SCRIPT).
#
# Usage :
#   bash infra/scripts/install_team_qa_smoke_job_vm.sh
#   LBG_CORE_VM_HOST=192.168.0.140 bash infra/scripts/install_team_qa_smoke_job_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-team-qa-smoke-job → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-qa-smoke-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-qa-smoke-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_qa_smoke
sudo chown lbg:lbg /var/lib/lbg/team_qa_smoke
sudo cp /tmp/lbg-team-qa-smoke-job.service /tmp/lbg-team-qa-smoke-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-qa-smoke-job.timer
sudo systemctl start lbg-team-qa-smoke-job.timer
systemctl is-active lbg-team-qa-smoke-job.timer
systemctl list-timers lbg-team-qa-smoke-job.timer --no-pager
EOF

echo ""
echo "Prérequis /etc/lbg-ia-mmo.env sur 140 :"
echo "  LBG_TEAM_ENABLED=1"
echo "  LBG_TEAM_QA_SMOKE_SCRIPT=/opt/LBG_IA_MMO/infra/scripts/smoke_vm_lan.sh"
echo "  LBG_TEAM_QA_SMOKE_TIMEOUT_S=300"
echo ""
echo "OK — tâches visibles sur http://192.168.0.110:8080/#/team (filtrer actor: system:team_qa_smoke)"
echo "Test manuel :"
echo "  ssh ${VM_USER}@${VM_HOST} 'sudo systemctl start lbg-team-qa-smoke-job.service && journalctl -u lbg-team-qa-smoke-job -n 30 --no-pager'"
