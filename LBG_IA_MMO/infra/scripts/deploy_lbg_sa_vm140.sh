#!/usr/bin/env bash
# Déploiement léger LBG Studios Agents (LBG_SA) sur VM core (140) :
# sync code, pip orchestrator, restart orchestrateur, kickoff Team.
#
# Usage :
#   bash infra/scripts/deploy_lbg_sa_vm140.sh
#   LBG_CORE_VM_HOST=192.168.0.140 LBG_SA_KICKOFF=1 bash infra/scripts/deploy_lbg_sa_vm140.sh
#   # équivalent canonique : LBG_STUDIOS_AGENTS_KICKOFF=1

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
REMOTE_STAGE="${LBG_VM_STAGE_DIR:-/home/${VM_USER}/.deploy/LBG_IA_MMO}"
ORCH_URL="${LBG_ORCHESTRATOR_URL:-http://${VM_HOST}:8010}"
KICKOFF="${LBG_STUDIOS_AGENTS_KICKOFF:-${LBG_SA_KICKOFF:-1}}"

SSH_OPTS=(
  -o ConnectTimeout=15
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_sa_%r@%h:%p"
)

RSYNC_EXCLUDES=(
  --exclude ".venv/"
  --exclude "**/__pycache__/"
  --exclude "**/*.pyc"
  --exclude "mmo_server/"
)

if [ "${LBG_SKIP_FIX_CRLF:-0}" != "1" ] && [ -f "${ROOT_DIR}/infra/scripts/fix_crlf.sh" ]; then
  bash "${ROOT_DIR}/infra/scripts/fix_crlf.sh" >/dev/null 2>&1 || true
fi

echo "=== LBG_SA deploy → ${VM_USER}@${VM_HOST}:${REMOTE_DIR} ==="

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "mkdir -p \"${REMOTE_STAGE}/docs\" \"${REMOTE_STAGE}/orchestrator\" \"${REMOTE_STAGE}/hybrid_proactive_agent\" \"${REMOTE_STAGE}/infra/secrets\""

rsync -a \
  "${RSYNC_EXCLUDES[@]}" \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/docs/plan_lbg_studios_agents_partitions.md" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/docs/"

rsync -a \
  "${RSYNC_EXCLUDES[@]}" \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/orchestrator/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/orchestrator/"

rsync -a \
  "${RSYNC_EXCLUDES[@]}" \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/hybrid_proactive_agent/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/hybrid_proactive_agent/"

rsync -a \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/infra/secrets/lbg.env.example" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/infra/secrets/"

ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
set -euo pipefail
sudo -n mkdir -p \"${REMOTE_DIR}/orchestrator\" \"${REMOTE_DIR}/docs\" \"${REMOTE_DIR}/hybrid_proactive_agent\"
sudo -n rsync -a \"${REMOTE_STAGE}/orchestrator/\" \"${REMOTE_DIR}/orchestrator/\"
sudo -n rsync -a \"${REMOTE_STAGE}/docs/plan_lbg_studios_agents_partitions.md\" \"${REMOTE_DIR}/docs/\"
sudo -n rsync -a \"${REMOTE_STAGE}/hybrid_proactive_agent/\" \"${REMOTE_DIR}/hybrid_proactive_agent/\"
sudo -n chown -R lbg:lbg \"${REMOTE_DIR}/orchestrator\" \"${REMOTE_DIR}/docs/plan_lbg_studios_agents_partitions.md\" \"${REMOTE_DIR}/hybrid_proactive_agent\"
sudo -n mkdir -p /var/lib/lbg-ia-mmo/lbg_sa/memory
sudo -n chown lbg:lbg /var/lib/lbg-ia-mmo/lbg_sa/memory
cd \"${REMOTE_DIR}\"
sudo -n -u lbg -H bash -c \"
  cd \\\"${REMOTE_DIR}\\\" && \
  .venv/bin/pip install -q -e ./hybrid_proactive_agent -e ./orchestrator
\"
sudo -n systemctl restart lbg-orchestrator
sleep 2
systemctl is-active lbg-orchestrator
'"

echo ""
echo "=== Smoke orchestrateur ==="
curl -sf "${ORCH_URL}/healthz" | head -c 200 || { echo "healthz KO"; exit 1; }
echo ""
curl -sf "${ORCH_URL}/v1/lbg_sa/meta" | python3 -m json.tool | head -n 25

if [ "${KICKOFF}" = "1" ]; then
  echo ""
  echo "=== Kickoff Team LBG_SA ==="
  curl -sf -X POST "${ORCH_URL}/v1/lbg_sa/team/kickoff" \
    -H "Content-Type: application/json" \
    -d "{\"actor_id\":\"system:lbg_sa-deploy\",\"force\":false}" | python3 -m json.tool
fi

echo ""
echo "OK — Pilot : http://${VM_HOST}:8080/#/team (ou LAN habituel)"
echo "Mémoire Atlas : /var/lib/lbg-ia-mmo/lbg_sa/memory/team__atlas.jsonl après run admin_infra"
