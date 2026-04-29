#!/usr/bin/env bash
set -euo pipefail

VM_HOST="${LBG_VM_HOST:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
# On déploie maintenant dans un sous-dossier de pilot_web pour Nginx
REMOTE_DIR="/opt/LBG_IA_MMO/pilot_web/mmo"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/../web_client"

echo "Compiling client with base /mmo/..."
cd "${CLIENT_DIR}"
npm run build -- --base=/mmo/

echo "Déploiement du client MMO vers ${VM_USER}@${VM_HOST}:${REMOTE_DIR}..."

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

# 1. Préparation du dossier et nettoyage de l'ancien service 8081
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "
  sudo systemctl stop lbg-web-client.service 2>/dev/null || true
  sudo systemctl disable lbg-web-client.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/lbg-web-client.service
  sudo systemctl daemon-reload
  sudo mkdir -p ${REMOTE_DIR}
  sudo chown -R ${VM_USER}:${VM_USER} ${REMOTE_DIR}
"

# 2. Rsync du dossier dist
rsync -a --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  "${CLIENT_DIR}/dist/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_DIR}/"

# 3. Redémarrage de Nginx pour prise en compte (optionnel mais recommandé)
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "sudo systemctl restart nginx"

# 4. Sync locale (pour visibilité dans l'explorateur)
echo "Synchronisation locale vers LBG_IA_MMO/pilot_web/mmo/..."
mkdir -p ../LBG_IA_MMO/pilot_web/mmo
rsync -avz --delete dist/ ../LBG_IA_MMO/pilot_web/mmo/

echo "Client MMO déployé et accessible sur http://192.168.0.110:8080/mmo/"
echo "L'interface Lyra reste sur http://${VM_HOST}:8080/"
