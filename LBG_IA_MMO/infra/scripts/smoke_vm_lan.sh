#!/usr/bin/env bash
# Smoke LAN — SSH sur les 3 VM : systemd (core + mmo), Ollama optionnel sur front.
# Prérequis : connexion SSH sans mot de passe vers LBG_VM_USER@VM (clé dans authorized_keys).
#
# Usage :
#   bash infra/scripts/smoke_vm_lan.sh
#
# Variables :
#   LBG_VM_USER              défaut : lbg
#   LBG_LAN_HOST_CORE|MMO|FRONT — défauts 192.168.0.140 / .245 / .110
#   LBG_SMOKE_CORE_SERVICES, LBG_SMOKE_MMO_SERVICES
#   LBG_SMOKE_FRONT_OLLAMA=1|0 (défaut 1)
#   LBG_SSH_IDENTITY         chemin vers une clé privée (ex. ~/.ssh/id_ed25519) si non utilisée par défaut
#   LBG_SSH_KNOWN_HOSTS_FILE chemin vers un fichier known_hosts écrivable (sinon mktemp)
#   LBG_SSH_BATCH=0          retire BatchMode=yes (permet saisie mot de passe SSH — déconseillé en routine)

set -euo pipefail

VM_USER="${LBG_VM_USER:-lbg}"
H_CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
H_MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
H_FRONT="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
SVC_CORE="${LBG_SMOKE_CORE_SERVICES:-lbg-backend lbg-orchestrator lbg-agent-dialogue lbg-agent-quests lbg-agent-combat}"
SVC_MMO="${LBG_SMOKE_MMO_SERVICES:-lbg-mmo-server lbg-mmmorpg-ws}"
CHECK_OLLAMA="${LBG_SMOKE_FRONT_OLLAMA:-1}"

# Éviter d'écrire dans ~/.ssh (peut être non accessible selon le contexte d'exécution).
# On force un known_hosts dans un chemin écrivable.
KNOWN_HOSTS_FILE="${LBG_SSH_KNOWN_HOSTS_FILE:-}"
if [[ -z "${KNOWN_HOSTS_FILE}" ]]; then
  KNOWN_HOSTS_FILE="$(mktemp -t lbg_known_hosts.XXXXXX)"
fi

SSH_OPTS=(
  -o ConnectTimeout=8
  -o LogLevel=ERROR
  -o StrictHostKeyChecking=accept-new
  -o UserKnownHostsFile="${KNOWN_HOSTS_FILE}"
  -o GlobalKnownHostsFile=/dev/null
)
if [[ "${LBG_SSH_BATCH:-1}" == "1" ]]; then
  SSH_OPTS+=( -o BatchMode=yes )
fi

if [[ -n "${LBG_SSH_IDENTITY:-}" ]]; then
  if [[ ! -f "${LBG_SSH_IDENTITY}" ]]; then
    echo "LBG_SSH_IDENTITY pointe vers un fichier absent : ${LBG_SSH_IDENTITY}" >&2
    exit 1
  fi
  SSH_OPTS=( -i "${LBG_SSH_IDENTITY}" "${SSH_OPTS[@]}" )
fi

fail=0
ssh_connect_failed=0

remote_active_all() {
  local label="$1"
  local host="$2"
  local services="$3"
  echo "=== ${label} (${host}) ==="
  if ! ssh "${SSH_OPTS[@]}" "${VM_USER}@${host}" "true"; then
    echo "  SSH indisponible — ${VM_USER}@${host}"
    ssh_connect_failed=1
    fail=1
    return
  fi
  # shellcheck disable=SC2086,SC2029
  if ! ssh "${SSH_OPTS[@]}" "${VM_USER}@${host}" bash -s <<EOF
set -euo pipefail
for svc in ${services}; do
  if ! sudo -n systemctl is-active "\$svc" >/dev/null 2>&1; then
    echo "  \${svc}: PAS active"
    exit 1
  fi
  echo "  \${svc}: active"
done
EOF
  then
    fail=1
  fi
}

remote_ollama() {
  local host="$1"
  echo "=== Front — Ollama (${host}) ==="
  if ! ssh "${SSH_OPTS[@]}" "${VM_USER}@${host}" "true"; then
    echo "  SSH indisponible — ${VM_USER}@${host}"
    ssh_connect_failed=1
    fail=1
    return
  fi
  # shellcheck disable=SC2029
  if ! ssh "${SSH_OPTS[@]}" "${VM_USER}@${host}" "curl -sf --connect-timeout 4 http://127.0.0.1:11434/api/tags >/dev/null"; then
    echo "  Ollama : indisponible sur :11434 (localhost VM)"
    fail=1
  else
    echo "  Ollama : OK (api/tags)"
  fi
}

echo "Smoke LAN — core ${H_CORE}, mmo ${H_MMO}, front ${H_FRONT} (utilisateur SSH : ${VM_USER})"
remote_active_all "Core" "${H_CORE}" "${SVC_CORE}"
remote_active_all "MMO" "${H_MMO}" "${SVC_MMO}"

if [[ "${CHECK_OLLAMA}" == "1" ]]; then
  remote_ollama "${H_FRONT}"
fi

if [[ "${fail}" -ne 0 ]]; then
  echo ""
  echo "Smoke LAN : échec (SSH, systemd ou Ollama)."
  if [[ "${ssh_connect_failed}" -eq 1 ]]; then
    echo ""
    echo "SSH — « Permission denied (publickey) » : la clé de ce poste doit être dans"
    echo "  /home/${VM_USER}/.ssh/authorized_keys sur chaque VM (voir docs/ops_vm_user.md)."
    echo "Vérifier :  ssh ${SSH_OPTS[*]} ${VM_USER}@${H_CORE}  (doit ouvrir une session sans mot de passe)"
    echo "Clé dédiée (fichier privé réel, ex. id_ed25519) :  LBG_SSH_IDENTITY=\$HOME/.ssh/id_ed25519 bash infra/scripts/smoke_vm_lan.sh"
    echo "« error in libcrypto » sur Load key : mauvais chemin ou fichier corrompu — pas le .pub, voir docs/ops_vm_user.md"
    echo "Autre compte Unix sur les VM :  LBG_VM_USER=ton_user bash infra/scripts/smoke_vm_lan.sh"
  fi
  exit 1
fi
echo ""
echo "Smoke LAN : OK."
