#!/usr/bin/env bash
set -euo pipefail

# Déploie le rôle "front" (pilot_web statique) + installe/active Nginx (same strategy que deploy_vm.sh).
#
# Prérequis :
# - SSH clé OK vers VM_USER@VM_HOST
# - VM_USER sudoer avec NOPASSWD (script utilise sudo -n)
#
# Usage :
#   LBG_VM_HOST=192.168.0.110 LBG_VM_USER=lbg LBG_NGINX_PILOT_PORT=8080 bash infra/scripts/deploy_front_nginx.sh
#
# Variables :
#   LBG_VM_HOST               défaut : 192.168.0.110
#   LBG_VM_USER               défaut : lbg
#   LBG_VM_SERVICE_USER       défaut : lbg
#   LBG_VM_DIR                défaut : /opt/LBG_IA_MMO
#   LBG_VM_STAGE_DIR          défaut : /home/<user>/.deploy/LBG_IA_MMO
#   LBG_NGINX_PILOT_PORT       défaut : 80 (mettre 8080 si :80 pris)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

VM_HOST="${LBG_VM_HOST:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
SERVICE_USER="${LBG_VM_SERVICE_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
REMOTE_STAGE_DIR="${LBG_VM_STAGE_DIR:-/home/${VM_USER}/.deploy/LBG_IA_MMO}"
LISTEN_PORT="${LBG_NGINX_PILOT_PORT:-80}"

CONF_LOCAL="${ROOT_DIR}/infra/nginx/pilot_web_110.conf.example"
SITE="lbg-pilot-110"

if [[ ! -d "${ROOT_DIR}/pilot_web" ]]; then
  echo "ERROR: ${ROOT_DIR}/pilot_web introuvable" >&2
  exit 1
fi
if [[ ! -f "${CONF_LOCAL}" ]]; then
  echo "ERROR: conf Nginx introuvable: ${CONF_LOCAL}" >&2
  exit 1
fi

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

echo "Deploy [front+nginx] -> ${VM_USER}@${VM_HOST}:${REMOTE_DIR} (listen :${LISTEN_PORT})"

# 1) Rsync pilot_web vers stage (user)
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc 'set -euo pipefail; mkdir -p \"${REMOTE_STAGE_DIR}/pilot_web\"'"
rsync -a --delete \
  --exclude ".venv/" \
  --exclude "**/__pycache__/" \
  --exclude "**/*.pyc" \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/pilot_web/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE_DIR}/pilot_web/"

# 2) Générer conf Nginx (port) et scp vers /tmp
TMP_CONF="$(mktemp)"
trap 'rm -f "${TMP_CONF}"' EXIT
sed "s/listen 80;/listen ${LISTEN_PORT};/" "${CONF_LOCAL}" > "${TMP_CONF}"
scp -q -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p" "${TMP_CONF}" "${VM_USER}@${VM_HOST}:/tmp/${SITE}.conf"

# 3) Promote stage -> /opt + install/enable nginx + conf (sudo -n)
ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  if ! sudo -n true 2>/dev/null; then
    echo \"ERROR: sudo demande un mot de passe (NOPASSWD requis).\" >&2
    exit 10
  fi

  sudo -n mkdir -p \"${REMOTE_DIR}/pilot_web\"
  sudo -n rsync -a --delete --exclude \"mmo/\" \"${REMOTE_STAGE_DIR}/pilot_web/\" \"${REMOTE_DIR}/pilot_web/\"
  sudo -n chown -R ${SERVICE_USER}:${SERVICE_USER} \"${REMOTE_DIR}/pilot_web\"

  sudo -n apt-get update -qq
  # Sur certaines VMs, sudoers interdit de propager DEBIAN_FRONTEND.
  sudo -n apt-get install -y -qq nginx
  sudo -n install -m 644 \"/tmp/${SITE}.conf\" \"/etc/nginx/sites-available/${SITE}\"
  sudo -n rm -f \"/tmp/${SITE}.conf\"
  sudo -n rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
  sudo -n ln -sf \"/etc/nginx/sites-available/${SITE}\" \"/etc/nginx/sites-enabled/${SITE}\"

  # Permissions lecture Nginx (www-data) sur /opt
  sudo -n chmod o+x /opt \"${REMOTE_DIR}\" 2>/dev/null || true
  sudo -n chmod -R o+rX \"${REMOTE_DIR}/pilot_web\" 2>/dev/null || true

  sudo -n nginx -t
  sudo -n systemctl enable nginx
  sudo -n systemctl restart nginx
'"

echo "OK — Front prêt."
if [[ "${LISTEN_PORT}" == "80" ]]; then
  echo "Pilot: http://${VM_HOST}/ — UI companion: http://${VM_HOST}/compagnon/ — API proxifiée: http://${VM_HOST}/companion-api/"
else
  echo "Pilot: http://${VM_HOST}:${LISTEN_PORT}/ — UI companion: http://${VM_HOST}:${LISTEN_PORT}/compagnon/ — API proxifiée: http://${VM_HOST}:${LISTEN_PORT}/companion-api/"
fi

