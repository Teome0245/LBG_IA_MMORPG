#!/usr/bin/env bash
# Parties root du setup Second Core3 — à lancer sur la VM 130/246 avec sudo.
# Depuis le poste de dev (invite mot de passe sdesharches) :
#   ssh -t sdesharches@192.168.0.130 'sudo bash -s' < infra/scripts/setup_core3_second_host_246_root_on_vm.sh
#
# Ou sur la VM : sudo bash setup_core3_second_host_246_root_on_vm.sh

set -euo pipefail

TARGET_IP="${LBG_SECOND_VM_IP:-192.168.0.246}"
GATEWAY="${LBG_LAN_GATEWAY:-192.168.0.254}"
VM_USER="${LBG_VM_USER:-lbg}"
PUBKEY="${LBG_BOOTSTRAP_PUBKEY:-ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJuOA6UrL08ihqzdxmqlGn0ANRxQvNfe8fM5KmT5v1R/ lbg@multi-vmn}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: exécuter en root (sudo bash …)" >&2
  exit 1
fi

echo "=== [root] Compte ${VM_USER} + sudo NOPASSWD ==="
if ! id "${VM_USER}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "LBG IA MMO" "${VM_USER}"
  usermod -aG sudo "${VM_USER}"
fi
install -d -m 700 -o "${VM_USER}" -g "${VM_USER}" "/home/${VM_USER}/.ssh"
AUTH="/home/${VM_USER}/.ssh/authorized_keys"
touch "${AUTH}"
chown "${VM_USER}:${VM_USER}" "${AUTH}"
chmod 600 "${AUTH}"
grep -qF "${PUBKEY}" "${AUTH}" || echo "${PUBKEY}" >> "${AUTH}"
SUDOERS="/etc/sudoers.d/lbg-nopasswd"
cat > "${SUDOERS}" <<'SUDO'
lbg ALL=(ALL) NOPASSWD:ALL
SUDO
chmod 440 "${SUDOERS}"
visudo -cf "${SUDOERS}"

CURRENT_IP="$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -1)"
if [[ "${CURRENT_IP}" != "${TARGET_IP}" ]]; then
  echo "=== [root] Migration IP ${CURRENT_IP} → ${TARGET_IP} ==="
  IFACE="$(ip route show default 2>/dev/null | awk '{print $5}' | head -1)"
  [[ -n "${IFACE}" ]] || IFACE="$(ip -o -4 addr show | awk '!/127.0.0.1/ {print $2; exit}')"
  mkdir -p /etc/netplan
  tee /etc/netplan/01-lbg-static.yaml >/dev/null <<YAML
network:
  version: 2
  ethernets:
    ${IFACE}:
      dhcp4: false
      addresses: [${TARGET_IP}/24]
      routes:
        - to: default
          via: ${GATEWAY}
      nameservers:
        addresses: [${GATEWAY}, 8.8.8.8]
YAML
  chmod 600 /etc/netplan/01-lbg-static.yaml
  netplan apply
  ip -4 -br addr show "${IFACE}"
fi

echo "=== [root] Répertoires /opt MMO ==="
mkdir -p /opt/lbg-new-mmo-clean/MMOCoreORB /opt/lbg-new-mmo/tre
PREP="/home/sdesharches/lbg-second-prep"
if [[ -d "${PREP}/MMOCoreORB" ]]; then
  echo "Promotion stack depuis ${PREP}…"
  rsync -a "${PREP}/MMOCoreORB/" /opt/lbg-new-mmo-clean/MMOCoreORB/
  [[ -d "${PREP}/tre" ]] && rsync -a "${PREP}/tre/" /opt/lbg-new-mmo/tre/
fi
chown -R "${VM_USER}:${VM_USER}" /opt/lbg-new-mmo-clean /opt/lbg-new-mmo

if [[ -f /home/sdesharches/lbg-core3-second.service ]]; then
  cp /home/sdesharches/lbg-core3-second.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable lbg-core3-second.service
fi

echo "OK — root setup terminé. Poursuivre depuis le poste de dev :"
echo "  LBG_SKIP_IP_MIGRATION=1 LBG_SECOND_VM_HOST=${TARGET_IP} bash infra/scripts/setup_core3_second_host_246_vm.sh"
