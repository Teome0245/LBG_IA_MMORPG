#!/usr/bin/env bash
# Installe le timer lbg-team-pm-reunification-job sur la VM core (140).
#
# Usage :
#   bash infra/scripts/install_team_pm_reunification_job_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-team-pm-reunification-job → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-pm-reunification-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-pm-reunification-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_pm_reunification
sudo chown lbg:lbg /var/lib/lbg/team_pm_reunification
sudo cp /tmp/lbg-team-pm-reunification-job.service /tmp/lbg-team-pm-reunification-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-pm-reunification-job.timer
sudo systemctl start lbg-team-pm-reunification-job.timer
systemctl is-active lbg-team-pm-reunification-job.timer
EOF

echo "OK — filtrer actor system:team_pm_reunification sur #/team"
