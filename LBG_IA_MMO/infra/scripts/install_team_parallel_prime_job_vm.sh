#!/usr/bin/env bash
# Installe le timer lbg-team-parallel-prime-job sur la VM core (140).
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
echo "=== Install lbg-team-parallel-prime-job → ${VM_USER}@${VM_HOST} ==="
scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-parallel-prime-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-parallel-prime-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"
ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_parallel_prime
sudo chown lbg:lbg /var/lib/lbg/team_parallel_prime
sudo cp /tmp/lbg-team-parallel-prime-job.service /tmp/lbg-team-parallel-prime-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-parallel-prime-job.timer
sudo systemctl start lbg-team-parallel-prime-job.timer
systemctl is-active lbg-team-parallel-prime-job.timer
EOF
echo "OK — actor system:team_parallel_prime (Vulcan + ZB-1 en parallèle)"
