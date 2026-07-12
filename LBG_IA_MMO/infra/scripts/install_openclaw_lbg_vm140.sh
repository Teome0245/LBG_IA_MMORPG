#!/usr/bin/env bash
# OpenClaw natif + bridge LBG sur VM core 140.
#
# - Bridge HTTP :127.0.0.1:18790 (contrat orchestrateur LBG_OPENCLAW_BASE_URL)
# - OpenClaw gateway natif optionnel :127.0.0.1:18789 (npm global)
# - Skills workspace ~/.openclaw/workspace/skills/lbg-*
#
# Usage :
#   bash infra/scripts/install_openclaw_lbg_vm140.sh
#   LBG_OPENCLAW_INSTALL_NATIVE=1 bash infra/scripts/install_openclaw_lbg_vm140.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
INSTALL_NATIVE="${LBG_OPENCLAW_INSTALL_NATIVE:-1}"

echo "=== OpenClaw LBG → ${VM_USER}@${VM_HOST} ==="

scp -q \
  "${ROOT_DIR}/infra/openclaw/lbg_skill_bridge.py" \
  "${ROOT_DIR}/infra/systemd/lbg-openclaw-bridge.service" \
  "${ROOT_DIR}/infra/openclaw/skills/"*.json \
  "${VM_USER}@${VM_HOST}:/tmp/"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p /opt/LBG_IA_MMO/infra/openclaw/skills
sudo cp /tmp/lbg_skill_bridge.py /opt/LBG_IA_MMO/infra/openclaw/
sudo cp /tmp/*.json /opt/LBG_IA_MMO/infra/openclaw/skills/ 2>/dev/null || true
sudo cp /tmp/lbg-openclaw-bridge.service /etc/systemd/system/

ENV_FILE=/etc/lbg-ia-mmo.env
touch_env() {
  local key="\$1" val="\$2"
  if sudo grep -q "^\${key}=" "\$ENV_FILE" 2>/dev/null; then
    sudo sed -i "s|^\${key}=.*|\${key}=\${val}|" "\$ENV_FILE"
  else
    echo "\${key}=\${val}" | sudo tee -a "\$ENV_FILE" >/dev/null
  fi
}
sudo touch "\$ENV_FILE"
touch_env LBG_OPENCLAW_ENABLED 1
touch_env LBG_OPENCLAW_BASE_URL http://127.0.0.1:18790
touch_env LBG_TEAM_OPS_USE_OPENCLAW 1
touch_env LBG_REASON_LOCAL_BASE_URL http://192.168.0.110:11434
touch_env LBG_REASON_FAILOVER 1
touch_env LBG_COMFYUI_BASE_URL http://192.168.0.10:8188

sudo systemctl daemon-reload
sudo systemctl enable lbg-openclaw-bridge.service
sudo systemctl restart lbg-openclaw-bridge.service
sleep 1
curl -sf http://127.0.0.1:18790/healthz | head -c 200
echo ""

if [[ "${INSTALL_NATIVE}" == "1" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_MAJOR=\$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
    if [[ "\$NODE_MAJOR" -ge 22 ]]; then
      echo "=== Install OpenClaw gateway natif (npm) ==="
      npm install -g openclaw@latest 2>/dev/null || echo "WARN: npm openclaw — installer manuellement si besoin"
      mkdir -p ~/.openclaw/workspace/skills
      for f in /opt/LBG_IA_MMO/infra/openclaw/skills/*.json; do
        [[ -f "\$f" ]] || continue
        id=\$(basename "\$f" .json)
        mkdir -p "\$HOME/.openclaw/workspace/skills/\$id"
        desc=\$(python3 -c "import json; print(json.load(open('\$f')).get('description','LBG skill'))" 2>/dev/null || echo "LBG ops skill")
        script=\$(python3 -c "import json; print(json.load(open('\$f')).get('script',''))" 2>/dev/null || echo "")
        cat > "\$HOME/.openclaw/workspace/skills/\$id/SKILL.md" <<SKILL
# \${id}

\${desc}

## Exécution LBG

Bridge HTTP : \`curl -X POST http://127.0.0.1:18790/v1/skills/\${id}/run\`

Script bash : \`/opt/LBG_IA_MMO/\${script}\`
SKILL
      done
      if command -v openclaw >/dev/null 2>&1; then
        openclaw gateway --port 18789 --bind 127.0.0.1 2>/dev/null &
        echo "OpenClaw gateway lancé en arrière-plan (127.0.0.1:18789) si non déjà actif"
      fi
    else
      echo "WARN: Node \$NODE_MAJOR < 22 — OpenClaw natif ignoré (bridge LBG actif). Upgrade: nvm install 22 && npm i -g openclaw"
    fi
  else
    echo "WARN: node absent — bridge LBG seul (suffisant pour orchestrateur)"
  fi
fi

systemctl is-active lbg-openclaw-bridge.service
EOF

echo "OK — LBG_OPENCLAW_BASE_URL=http://127.0.0.1:18790 sur ${VM_HOST}"
