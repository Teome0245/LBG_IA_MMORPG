#!/usr/bin/env bash
set -euo pipefail

# Déploiement ciblé du monorepo LBG_IA_MMO vers une ou plusieurs VM (réseau privé).
#
# Rôles (LBG_DEPLOY_ROLE) :
#   core  — backend, orchestrator, agents, pilot_web (optionnel) ; **sans** mmo_server/ sur le disque
#   mmo   — **mmo_server** (HTTP Lyra) + **mmmorpg_server** (WebSocket jeu) + unités systemd associées
#   front — **pilot_web/** statique uniquement (ex. VM 110 ; API reste sur core)
#   all   — enchaîne core → mmo → front sur les hôtes LBG_LAN_HOST_* (voir ci‑dessous)
#
# Prérequis : compte SSH (défaut lbg) **sudoer** sur chaque VM cible.
#
# Usage :
#   bash infra/scripts/deploy_vm.sh
#   LBG_DEPLOY_ROLE=core LBG_VM_HOST=192.168.0.140 LBG_VM_USER=lbg bash infra/scripts/deploy_vm.sh
#   LBG_DEPLOY_ROLE=mmo  LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg bash infra/scripts/deploy_vm.sh
#   LBG_DEPLOY_ROLE=front LBG_VM_HOST=192.168.0.110 LBG_VM_USER=lbg bash infra/scripts/deploy_vm.sh
#   LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh
#
# Pilot sur une autre machine que le core : avant deploy core, export
#   LBG_PILOT_WEB_ON_FRONT=1
# pour **exclure** pilot_web du sync 140 (le rôle **front** déploie pilot_web sur 110).
#
# CRLF : par défaut, exécute `infra/scripts/fix_crlf.sh` avant rsync (opt-out via LBG_SKIP_FIX_CRLF=1).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

DEPLOY_ROLE="${LBG_DEPLOY_ROLE:-core}"
VM_HOST="${LBG_VM_HOST:-192.168.0.140}"
VM_USER="${LBG_VM_USER:-lbg}"
SERVICE_USER="${LBG_VM_SERVICE_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
REMOTE_STAGE_DIR="${LBG_VM_STAGE_DIR:-/home/${VM_USER}/.deploy/LBG_IA_MMO}"

# Prévenir les erreurs `pipefail\r` : corrige les fins de lignes CRLF localement
# avant rsync (opt-out via LBG_SKIP_FIX_CRLF=1).
if [ "${LBG_SKIP_FIX_CRLF:-0}" != "1" ]; then
  if [ -f "${ROOT_DIR}/infra/scripts/fix_crlf.sh" ]; then
    bash "${ROOT_DIR}/infra/scripts/fix_crlf.sh" >/dev/null 2>&1 || true
  fi
fi

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

if [ "${DEPLOY_ROLE}" = "all" ]; then
  echo "=== deploy LAN séquentiel : core → mmo → front ==="
  _WANT_PUSH="${LBG_PUSH_SECRETS:-0}"
  LBG_PUSH_SECRETS=0 LBG_VM_HOST="${LBG_LAN_HOST_CORE:-192.168.0.140}" LBG_DEPLOY_ROLE=core \
    LBG_PILOT_WEB_ON_FRONT="${LBG_PILOT_WEB_ON_FRONT:-1}" \
    bash "${SCRIPT_PATH}"
  LBG_PUSH_SECRETS=0 LBG_VM_HOST="${LBG_LAN_HOST_MMO:-192.168.0.245}" LBG_DEPLOY_ROLE=mmo \
    bash "${SCRIPT_PATH}"
  LBG_PUSH_SECRETS=0 LBG_VM_HOST="${LBG_LAN_HOST_FRONT:-192.168.0.110}" LBG_DEPLOY_ROLE=front \
    bash "${SCRIPT_PATH}"
  if [ "${_WANT_PUSH}" = "1" ]; then
    SEC_FILE="${LBG_SECRETS_FILE:-${ROOT_DIR}/infra/secrets/lbg.env}"
    if [ -f "${SEC_FILE}" ]; then
      echo "=== push secrets → LAN (${LBG_LAN_HOST_CORE:-192.168.0.140}, ${LBG_LAN_HOST_MMO:-192.168.0.245}, ${LBG_LAN_HOST_FRONT:-192.168.0.110}) ==="
      LBG_SECRETS_FILE="${SEC_FILE}" LBG_VM_USER="${LBG_VM_USER:-lbg}" \
        LBG_VM_HOSTS="${LBG_LAN_HOST_CORE:-192.168.0.140} ${LBG_LAN_HOST_MMO:-192.168.0.245} ${LBG_LAN_HOST_FRONT:-192.168.0.110}" \
        bash "${ROOT_DIR}/infra/scripts/push_secrets_vm.sh"
    fi
  fi
  echo "=== all : terminé ==="
  exit 0
fi

echo "Deploy [${DEPLOY_ROLE}] -> ${VM_USER}@${VM_HOST}:${REMOTE_DIR}"

# --- rsync : exclusions selon rôle (évite de dédoubler inutilement sur chaque VM) ---
RSYNC_EXCLUDES=(
  --exclude ".venv/"
  --exclude "**/__pycache__/"
  --exclude "**/*.pyc"
)

case "${DEPLOY_ROLE}" in
  core)
    RSYNC_EXCLUDES+=(--exclude "mmo_server/")
    if [ "${LBG_PILOT_WEB_ON_FRONT:-0}" = "1" ]; then
      RSYNC_EXCLUDES+=(--exclude "pilot_web/")
      echo "Note: pilot_web exclu (déployer le rôle front sur LBG_LAN_HOST_FRONT)"
    fi
    ;;
  mmo)
    RSYNC_EXCLUDES+=(
      --exclude "backend/"
      --exclude "orchestrator/"
      --exclude "agents/"
      --exclude "pilot_web/"
    )
    ;;
  front)
    : # rsync dédié plus bas
    ;;
  *)
    echo "ERROR: LBG_DEPLOY_ROLE inconnu: ${DEPLOY_ROLE} (attendu: core|mmo|front|all)" >&2
    exit 1
    ;;
esac

# --- Rôle front : uniquement pilot_web ---
if [ "${DEPLOY_ROLE}" = "front" ]; then
  if [ ! -d "${ROOT_DIR}/pilot_web" ]; then
    echo "ERROR: ${ROOT_DIR}/pilot_web introuvable" >&2
    exit 1
  fi
  ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc 'set -euo pipefail; mkdir -p \"${REMOTE_STAGE_DIR}/pilot_web\"'"
  rsync -a --delete \
    "${RSYNC_EXCLUDES[@]}" \
    -e "ssh ${SSH_OPTS[*]}" \
    "${ROOT_DIR}/pilot_web/" \
    "${VM_USER}@${VM_HOST}:${REMOTE_STAGE_DIR}/pilot_web/"
  ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
    set -euo pipefail
    sudo -n mkdir -p \"${REMOTE_DIR}/pilot_web\"
    sudo -n rsync -a --delete \"${REMOTE_STAGE_DIR}/pilot_web/\" \"${REMOTE_DIR}/pilot_web/\"
    sudo -n chown -R ${SERVICE_USER}:${SERVICE_USER} \"${REMOTE_DIR}/pilot_web\"
  '"
  echo "Front (pilot_web) déployé vers ${REMOTE_DIR}/pilot_web — configurer Nginx ou servir les fichiers ; API : LBG backend sur le host core (ex. http://192.168.0.140:8000)."
  exit 0
fi

# --- core & mmo : sync arborescence filtrée ---
echo "Sync (stage) -> ${VM_USER}@${VM_HOST}:${REMOTE_STAGE_DIR}"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
  set -euo pipefail
  mkdir -p \"${REMOTE_STAGE_DIR}\"
'"

rsync -a --delete \
  "${RSYNC_EXCLUDES[@]}" \
  -e "ssh ${SSH_OPTS[*]}" \
  "${ROOT_DIR}/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE_DIR}/"

# --- Installation & systemd distants (core vs mmo) ---
REMOTE_PROMOTE=$(cat <<EOF
  set -euo pipefail
  echo "Promote stage -> ${REMOTE_DIR}"
  sudo -n mkdir -p "${REMOTE_DIR}"
  sudo -n rsync -a --delete "${REMOTE_STAGE_DIR}/" "${REMOTE_DIR}/"
  cd "${REMOTE_DIR}"
  if command -v sed >/dev/null 2>&1; then
    sudo -n sed -i "s/\\r\$//" infra/scripts/*.sh 2>/dev/null || true
  fi
EOF
)

if [ "${DEPLOY_ROLE}" = "core" ]; then
  # shellcheck disable=SC2029
  ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
${REMOTE_PROMOTE}
  if [ ! -f infra/scripts/install_local.sh ]; then echo ERROR install_local.sh; exit 1; fi
  if ! python3 -c \"import ensurepip\" >/dev/null 2>&1; then
    v=\"\$(python3 -V 2>/dev/null)\"; v=\"\${v#Python }\"; PY_VER=\"\${v%.*}\"
    if [ -z \"\${PY_VER}\" ]; then echo ERROR python; exit 1; fi
    sudo -n apt-get update
    sudo -n apt-get install -y \"python\${PY_VER}-venv\" python3-venv
  fi
  sudo -n chown -R ${SERVICE_USER}:${SERVICE_USER} \"${REMOTE_DIR}\"
  sudo -n -u ${SERVICE_USER} -H bash -c \"cd \\\"${REMOTE_DIR}\\\" && LBG_SKIP_MMO_SERVER=1 bash infra/scripts/install_local.sh\"
  for u in lbg-agent-dialogue.service lbg-agent-quests.service lbg-agent-combat.service lbg-orchestrator.service lbg-backend.service; do
    if [ ! -f \"infra/systemd/\$u\" ]; then echo ERROR missing \$u; exit 1; fi
    sudo -n cp \"infra/systemd/\$u\" /etc/systemd/system/
  done
  sudo -n systemctl daemon-reload
  for u in lbg-agent-dialogue lbg-agent-quests lbg-agent-combat lbg-orchestrator lbg-backend; do
    sudo -n systemctl enable --now \"\$u\"
    sudo -n systemctl restart \"\$u\"
  done
'"

elif [ "${DEPLOY_ROLE}" = "mmo" ]; then
  # shellcheck disable=SC2029
  ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
${REMOTE_PROMOTE}
  if [ ! -f infra/scripts/install_local_mmo.sh ]; then echo ERROR install_local_mmo.sh; exit 1; fi
  if ! python3 -c \"import ensurepip\" >/dev/null 2>&1; then
    v=\"\$(python3 -V 2>/dev/null)\"; v=\"\${v#Python }\"; PY_VER=\"\${v%.*}\"
    sudo -n apt-get update
    sudo -n apt-get install -y \"python\${PY_VER}-venv\" python3-venv
  fi
  sudo -n chown -R ${SERVICE_USER}:${SERVICE_USER} \"${REMOTE_DIR}\"
  sudo -n -u ${SERVICE_USER} -H bash -c \"cd \\\"${REMOTE_DIR}\\\" && bash infra/scripts/install_local_mmo.sh\"
  if [ ! -f infra/systemd/lbg-mmo-server.service ]; then echo ERROR lbg-mmo-server.service; exit 1; fi
  if [ ! -f infra/systemd/lbg-mmmorpg-ws.service ]; then echo ERROR lbg-mmmorpg-ws.service; exit 1; fi
  sudo -n cp infra/systemd/lbg-mmo-server.service /etc/systemd/system/
  sudo -n cp infra/systemd/lbg-mmmorpg-ws.service /etc/systemd/system/
  sudo -n systemctl daemon-reload
  sudo -n systemctl enable --now lbg-mmo-server
  sudo -n systemctl restart lbg-mmo-server
  sudo -n systemctl enable --now lbg-mmmorpg-ws
  sudo -n systemctl restart lbg-mmmorpg-ws
'"
fi

# Pousser les secrets (optionnel)
if [ "${LBG_PUSH_SECRETS:-0}" = "1" ]; then
  SEC_FILE="${LBG_SECRETS_FILE:-${ROOT_DIR}/infra/secrets/lbg.env}"
  if [ -f "${SEC_FILE}" ]; then
    LBG_SECRETS_FILE="${SEC_FILE}" LBG_VM_HOST="${VM_HOST}" LBG_VM_USER="${VM_USER}" bash "${ROOT_DIR}/infra/scripts/push_secrets_vm.sh"
  else
    echo "WARN: LBG_PUSH_SECRETS=1 mais fichier absent : ${SEC_FILE} (skip)" >&2
  fi
fi

echo "Done [${DEPLOY_ROLE}]."
