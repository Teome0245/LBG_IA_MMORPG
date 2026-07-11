#!/usr/bin/env bash
# Installe le timer lbg-team-player-ia-job sur la VM core (140).
#
# Usage :
#   bash infra/scripts/install_team_player_ia_job_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"

echo "=== Install lbg-team-player-ia-job → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-player-ia-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-player-ia-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_player_ia
sudo chown lbg:lbg /var/lib/lbg/team_player_ia
sudo cp /tmp/lbg-team-player-ia-job.service /tmp/lbg-team-player-ia-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-player-ia-job.timer
sudo systemctl start lbg-team-player-ia-job.timer
systemctl is-active lbg-team-player-ia-job.timer
EOF

echo "Prérequis /etc/lbg-ia-mmo.env : LBG_CORE3_SIDECAR_URL=http://192.168.0.246:8791"
echo "OK — filtrer actor system:team_player_ia sur #/team"
