#!/usr/bin/env bash
set -euo pipefail

# Pousse un fichier d'environnement local vers une ou plusieurs VM : /etc/lbg-ia-mmo.env
# (lu par systemd via EnvironmentFile= dans les unités lbg-*.service).
# Si tu répliques le même fichier sur 140 / 245 / 110, utiliser les IP LAN pour le core
# (orchestrateur + agents → 192.168.0.140), pas 127.0.0.1 — voir docs/fusion_env_lan.md.
#
# Ne jamais committer le fichier source : rester hors dépôt ou dans infra/secrets/lbg.env (gitignore).
#
# Usage :
#   cp infra/secrets/lbg.env.example infra/secrets/lbg.env   # une fois, puis éditer
#   bash infra/scripts/push_secrets_vm.sh
#     # → par défaut : les 3 hôtes LAN (LBG_LAN_HOST_CORE / MMO / FRONT)
#
#   LBG_VM_HOST=192.168.0.140 bash infra/scripts/push_secrets_vm.sh    # une seule VM
#   LBG_VM_HOSTS="192.168.0.140 192.168.0.245" bash infra/scripts/push_secrets_vm.sh
#
# Priorité des cibles : LBG_VM_HOSTS (liste) > LBG_VM_HOST (une IP) > défaut 3 VM.
#
# Options :
#   LBG_VM_HOSTS — espaces : plusieurs hôtes (prioritaire si non vide)
#   LBG_VM_HOST — une seule cible (si LBG_VM_HOSTS vide)
#   LBG_LAN_HOST_CORE, LBG_LAN_HOST_MMO, LBG_LAN_HOST_FRONT — défauts 192.168.0.140 / .245 / .110
#   LBG_VM_USER — comme deploy_vm.sh (défaut : lbg)
#   LBG_SECRETS_GROUP — groupe du fichier env (défaut : lbg)
#   LBG_SECRETS_FILE — défaut : <racine monorepo>/infra/secrets/lbg.env
#   LBG_RESTART_SERVICES=1 — redémarrer les services lbg-* après chaque copie (défaut : 1)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_USER="${LBG_VM_USER:-lbg}"
SECRETS_GROUP="${LBG_SECRETS_GROUP:-lbg}"
LOCAL="${LBG_SECRETS_FILE:-${ROOT_DIR}/infra/secrets/lbg.env}"
RESTART="${LBG_RESTART_SERVICES:-1}"

LAN_CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
LAN_MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
LAN_FRONT="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
DEFAULT_HOSTS="${LAN_CORE} ${LAN_MMO} ${LAN_FRONT}"

if [ -n "${LBG_VM_HOSTS:-}" ]; then
  TARGETS="${LBG_VM_HOSTS}"
elif [ -n "${LBG_VM_HOST:-}" ]; then
  TARGETS="${LBG_VM_HOST}"
else
  TARGETS="${DEFAULT_HOSTS}"
fi

if [ ! -f "${LOCAL}" ]; then
  echo "Fichier introuvable : ${LOCAL}" >&2
  echo "Créez-le (ex. cp infra/secrets/lbg.env.example infra/secrets/lbg.env) puis relancez." >&2
  exit 1
fi

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

push_one() {
  local VM_HOST="$1"
  local REMOTE_TMP="lbg-ia-mmo.env.$$"
  echo "Push secrets -> ${VM_USER}@${VM_HOST}:/etc/lbg-ia-mmo.env (depuis ${LOCAL})"

  scp "${SSH_OPTS[@]}" "${LOCAL}" "${VM_USER}@${VM_HOST}:/tmp/${REMOTE_TMP}"

  # Session SSH unique. On évite `sudo -v` (qui peut forcer un prompt) et on s'appuie
  # uniquement sur `sudo -n <cmd>` : si la VM est configurée en NOPASSWD, aucun prompt.
  ssh -tt "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -lc '
    set -euo pipefail
    sudo -n install -m 640 -o root -g ${SECRETS_GROUP} \"/tmp/${REMOTE_TMP}\" /etc/lbg-ia-mmo.env
    sudo -n rm -f \"/tmp/${REMOTE_TMP}\"
    echo \"OK: /etc/lbg-ia-mmo.env (640 root:${SECRETS_GROUP})\"
    if [ \"${RESTART}\" = \"1\" ]; then
      echo \"Restart services (unités présentes uniquement)…\"
      for svc in lbg-agent-dialogue lbg-agent-quests lbg-agent-combat lbg-orchestrator lbg-backend lbg-mmo-server lbg-mmmorpg-ws; do
        if sudo -n systemctl cat \"\${svc}.service\" >/dev/null 2>&1; then
          sudo -n systemctl restart \"\${svc}\"
        fi
      done
      echo OK
    fi
  '"
}

for VM_HOST in ${TARGETS}; do
  push_one "${VM_HOST}"
done

echo "Done (${TARGETS})."
