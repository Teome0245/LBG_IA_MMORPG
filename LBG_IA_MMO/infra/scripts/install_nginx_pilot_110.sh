#!/usr/bin/env bash
# Installe Nginx sur la VM « front » (pilot statique) et active la conf pilot.
# Prérequis : SSH vers LBG_VM_USER@LBG_LAN_HOST_FRONT (clé), sudo sur la VM.
#
# Usage : depuis ton POSTE DE DEV (clone du monorepo) — le rôle deploy « front » ne pousse
# que pilot_web sur la VM, pas infra/scripts ; ce script doit tourner sur le PC :
#   cd LBG_IA_MMO && bash infra/scripts/install_nginx_pilot_110.sh
#
# Si :80 est pris par Docker (docker-proxy) :
#   LBG_NGINX_PILOT_PORT=8080 bash infra/scripts/install_nginx_pilot_110.sh
#
# Variables :
#   LBG_LAN_HOST_FRONT      défaut : 192.168.0.110
#   LBG_VM_USER             défaut : lbg
#   LBG_NGINX_PILOT_PORT    défaut : 80 — ex. 8080 si docker-proxy occupe déjà :80
#   LBG_SSH_IDENTITY        optionnel : chemin clé privée
#   LBG_SSH_BATCH=0         retire BatchMode (mot de passe SSH)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_USER="${LBG_VM_USER:-lbg}"
VM_HOST="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
LISTEN_PORT="${LBG_NGINX_PILOT_PORT:-80}"
CONF_LOCAL="${ROOT_DIR}/infra/nginx/pilot_web_110.conf.example"
REMOTE_TMP="lbg-pilot-nginx.$$"
SITE="lbg-pilot-110"

SSH_OPTS=( -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new )
if [[ "${LBG_SSH_BATCH:-1}" == "1" ]]; then
  SSH_OPTS+=( -o BatchMode=yes )
fi
if [[ -n "${LBG_SSH_IDENTITY:-}" ]]; then
  [[ -f "${LBG_SSH_IDENTITY}" ]] || { echo "Fichier clé absent : ${LBG_SSH_IDENTITY}" >&2; exit 1; }
  SSH_OPTS=( -i "${LBG_SSH_IDENTITY}" "${SSH_OPTS[@]}" )
fi

if [[ ! -f "${CONF_LOCAL}" ]]; then
  echo "Fichier introuvable : ${CONF_LOCAL}" >&2
  exit 1
fi

TMP_CONF="$(mktemp)"
trap 'rm -f "${TMP_CONF}"' EXIT
sed "s/listen 80;/listen ${LISTEN_PORT};/" "${CONF_LOCAL}" > "${TMP_CONF}"

echo "Nginx pilot — ${VM_USER}@${VM_HOST} (port ${LISTEN_PORT}, conf dérivée de ${CONF_LOCAL})"

scp "${SSH_OPTS[@]}" "${TMP_CONF}" "${VM_USER}@${VM_HOST}:/tmp/${REMOTE_TMP}"

REMOTE_SCRIPT=$(cat <<EOS
set -euo pipefail
echo "Sudo auth (VM front)"
sudo -v
sudo -n apt-get update -qq
sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
sudo -n install -m 644 /tmp/${REMOTE_TMP} /etc/nginx/sites-available/${SITE}
sudo -n rm -f /tmp/${REMOTE_TMP}
sudo -n rm -f /etc/nginx/sites-enabled/default
sudo -n ln -sf /etc/nginx/sites-available/${SITE} /etc/nginx/sites-enabled/${SITE}
if [[ -d /opt/LBG_IA_MMO ]]; then
  sudo -n chmod o+x /opt /opt/LBG_IA_MMO 2>/dev/null || true
fi
if [[ -d /opt/LBG_IA_MMO/pilot_web ]]; then
  sudo -n chmod -R o+rX /opt/LBG_IA_MMO/pilot_web
fi
sudo -n nginx -t
sudo -n systemctl enable nginx
if ! sudo -n systemctl restart nginx; then
  echo "=== Échec restart nginx ===" >&2
  sudo -n ss -tlnp 2>/dev/null | grep -E ':80|:8080' || true
  echo "--- journalctl nginx ---" >&2
  sudo -n journalctl -xeu nginx.service --no-pager -n 40 >&2 || true
  exit 1
fi
echo "OK: Nginx :${LISTEN_PORT} -> /opt/LBG_IA_MMO/pilot_web"
EOS
)

ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc $(printf '%q' "${REMOTE_SCRIPT}")"

echo ""
if [[ "${LISTEN_PORT}" == "80" ]]; then
  echo "Rappel — CORS sur le backend (VM 140), ex. :"
  echo "  LBG_CORS_ORIGINS=\"http://${VM_HOST},http://${VM_HOST}:80\""
else
  echo "Rappel — CORS sur le backend (VM 140) — inclure le port ${LISTEN_PORT} :"
  echo "  LBG_CORS_ORIGINS=\"http://${VM_HOST}:${LISTEN_PORT}\""
fi
echo "puis : LBG_VM_HOSTS=192.168.0.140 bash infra/scripts/push_secrets_vm.sh"
echo "Pilot : http://${VM_HOST}:${LISTEN_PORT}/ — API : http://192.168.0.140:8000"
