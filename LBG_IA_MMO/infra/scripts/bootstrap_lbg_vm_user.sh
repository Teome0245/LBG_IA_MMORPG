#!/usr/bin/env bash
# Crée le compte service lbg + clé SSH + sudo NOPASSWD (aligné 140/245/110).
# À lancer sur la VM cible avec un compte sudo (ex. sdesharches).
#
# Usage local :
#   LBG_BOOTSTRAP_USER=sdesharches LBG_VM_HOST=192.168.0.130 bash infra/scripts/bootstrap_lbg_vm_user.sh
#
# Usage avec mot de passe sudo (non interactif) :
#   LBG_VM_SUDO_PASSWORD='…' LBG_BOOTSTRAP_USER=sdesharches LBG_VM_HOST=192.168.0.130 bash infra/scripts/bootstrap_lbg_vm_user.sh

set -euo pipefail

VM_HOST="${LBG_VM_HOST:?LBG_VM_HOST requis}"
BOOTSTRAP_USER="${LBG_BOOTSTRAP_USER:-sdesharches}"
VM_USER="${LBG_VM_USER:-lbg}"
SSH_IDENTITY="${LBG_SSH_IDENTITY:-${HOME}/.ssh/id_ed25519}"
SUDO_PASS="${LBG_VM_SUDO_PASSWORD:-}"

if [[ ! -f "${SSH_IDENTITY}.pub" ]]; then
  echo "ERROR: clé publique absente : ${SSH_IDENTITY}.pub" >&2
  exit 1
fi

PUBKEY="$(cat "${SSH_IDENTITY}.pub")"

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_bootstrap_%r@%h:%p")

remote_sudo() {
  local script="$1"
  if [[ -n "${SUDO_PASS}" ]]; then
    printf '%s\n' "${SUDO_PASS}" | ssh "${SSH_OPTS[@]}" "${BOOTSTRAP_USER}@${VM_HOST}" \
      "sudo -S bash -s" <<<"${script}"
  else
    ssh -tt "${SSH_OPTS[@]}" "${BOOTSTRAP_USER}@${VM_HOST}" "sudo bash -s" <<<"${script}"
  fi
}

echo "=== Bootstrap ${VM_USER} sur ${VM_HOST} (via ${BOOTSTRAP_USER}) ==="

if ssh "${SSH_OPTS[@]}" -o BatchMode=yes -o ConnectTimeout=8 "${VM_USER}@${VM_HOST}" "echo ok" >/dev/null 2>&1; then
  echo "OK — ${VM_USER}@${VM_HOST} déjà accessible en SSH BatchMode."
  exit 0
fi

remote_sudo "$(cat <<EOS
set -euo pipefail
VM_USER="${VM_USER}"
PUBKEY='${PUBKEY}'

if ! id "\${VM_USER}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "LBG IA MMO" "\${VM_USER}"
  usermod -aG sudo "\${VM_USER}"
fi

install -d -m 700 -o "\${VM_USER}" -g "\${VM_USER}" "/home/\${VM_USER}/.ssh"
AUTH="/home/\${VM_USER}/.ssh/authorized_keys"
touch "\${AUTH}"
chown "\${VM_USER}:\${VM_USER}" "\${AUTH}"
chmod 600 "\${AUTH}"
grep -qF "\${PUBKEY}" "\${AUTH}" || echo "\${PUBKEY}" >> "\${AUTH}"

SUDOERS="/etc/sudoers.d/lbg-nopasswd"
cat > "\${SUDOERS}" <<'SUDO'
lbg ALL=(ALL) NOPASSWD:ALL
SUDO
chmod 440 "\${SUDOERS}"
visudo -cf "\${SUDOERS}"

echo "Bootstrap OK — user \${VM_USER}"
EOS
)"

if ssh "${SSH_OPTS[@]}" -o BatchMode=yes -o ConnectTimeout=8 "${VM_USER}@${VM_HOST}" "sudo -n true && echo sudo_nopass_ok" >/dev/null 2>&1; then
  echo "OK — ${VM_USER}@${VM_HOST} prêt (SSH + sudo NOPASSWD)."
else
  echo "WARN — ${VM_USER} créé mais sudo NOPASSWD non vérifié (BatchMode)." >&2
  exit 1
fi
