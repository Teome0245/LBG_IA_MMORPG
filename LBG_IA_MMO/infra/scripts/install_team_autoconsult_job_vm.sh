#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
echo "=== Install lbg-team-autoconsult-job → ${VM_USER}@${VM_HOST} (timer 12h) ==="
scp -q \
  "${ROOT_DIR}/infra/systemd/lbg-team-autoconsult-job.service" \
  "${ROOT_DIR}/infra/systemd/lbg-team-autoconsult-job.timer" \
  "${VM_USER}@${VM_HOST}:/tmp/"
ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'EOF'
set -euo pipefail
sudo mkdir -p /var/lib/lbg/team_autoconsult
sudo chown lbg:lbg /var/lib/lbg/team_autoconsult
sudo cp /tmp/lbg-team-autoconsult-job.service /tmp/lbg-team-autoconsult-job.timer /etc/systemd/system/
# Variables recommandées (append idempotent)
ENV_FILE=/etc/lbg-ia-mmo.env
touch_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sudo sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" | sudo tee -a "$ENV_FILE" >/dev/null
  fi
}
sudo touch "$ENV_FILE"
touch_env LBG_TEAM_AUTOCONSULT_JOB_ENABLED 1
touch_env LBG_TEAM_AUTOCONSULT_JOB_COOLDOWN_S 43200
touch_env LBG_TEAM_AUTOCONSULT_FOLLOWUP_AUTO_RUN 1
touch_env LBG_TEAM_M9_AUTO_REMEDIATE 1
touch_env LBG_PRIME_CLIENT_ROOT /opt/new_mmo/prime-client
touch_env LBG_TEAM_OPS_USE_OPENCLAW 1
touch_env LBG_IRIS_FORGE_LLM 1
touch_env LBG_IRIS_FORGE_SMOKE_REQUIRED 1
touch_env LBG_REASON_BASE_URL http://192.168.0.110:11434
sudo systemctl daemon-reload
sudo systemctl enable lbg-team-autoconsult-job.timer
sudo systemctl restart lbg-team-autoconsult-job.timer
systemctl is-active lbg-team-autoconsult-job.timer
systemctl list-timers 'lbg-team-autoconsult*' --no-pager
EOF
echo "OK — autoconsult 12h · doc architecture_tri_backend_hybride.md"