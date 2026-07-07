#!/usr/bin/env bash
# Bootstrap Claude Code + outillage build sur la VM core 140 (lbg-backend).
#
# Rôle cible de 140 : backend prod (systemd) + poste Claude Code (tmux) à terme.
#
# Usage (sur 140, compte lbg) :
#   cd /opt/LBG_IA_MMO && bash infra/scripts/bootstrap_claude_on_core140.sh
#
# Depuis le poste de dev (WSL) :
#   ssh lbg@192.168.0.140 'bash -s' < infra/scripts/bootstrap_claude_on_core140.sh
#
# Après redimension Proxmox (voir docs/fusion_env_lan.md § VM 140) :
#   sudo growpart /dev/sda 3 && sudo resize2fs /dev/sda3   # adapter partition si besoin
#
# Prérequis : sudo pour apt ; auth Claude (`claude login`) manuelle une fois par utilisateur.

set -euo pipefail

CORE_IP="${LBG_LAN_HOST_CORE:-192.168.0.140}"
FRONT_IP="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
APP_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
TARGET_USER="${LBG_BOOTSTRAP_USER:-lbg}"

log() { echo "[bootstrap_claude_140] $*"; }

warn_host() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -n "$ip" && "$ip" != "$CORE_IP" ]]; then
    log "AVERTISSEMENT : IP locale ${ip} ≠ ${CORE_IP} — continuer quand même ? (Ctrl+C pour annuler)"
    sleep 3
  fi
}

need_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=""
  elif sudo -n true 2>/dev/null; then
    SUDO="sudo -n"
  else
    log "sudo requis pour apt — lancez avec un compte sudoer ou : sudo bash $0"
    exit 1
  fi
}

install_apt_base() {
  log "Paquets de base (git, tmux, curl, build-essential)…"
  $SUDO apt-get update -qq
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    git tmux curl ca-certificates build-essential jq
}

install_node() {
  if command -v node >/dev/null 2>&1; then
    log "Node déjà présent : $(node -v)"
    return
  fi
  log "Installation Node.js 20.x (nodesource)…"
  curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
  log "Node : $(node -v) — npm : $(npm -v)"
}

install_claude_for_user() {
  local user="$1"
  local home
  home="$(getent passwd "$user" | cut -d: -f6)"
  if [[ -z "$home" || ! -d "$home" ]]; then
    log "Utilisateur ${user} introuvable — skip Claude"
    return
  fi

  if sudo -u "$user" bash -lc 'command -v claude >/dev/null 2>&1'; then
    log "Claude déjà installé pour ${user} : $(sudo -u "$user" bash -lc 'claude --version 2>/dev/null || true')"
    return
  fi

  log "Installation Claude Code pour ${user}…"
  sudo -u "$user" bash -lc 'curl -fsSL https://claude.ai/install.sh | bash'
  log "→ Connectez-vous une fois : sudo -u ${user} -i claude login"
}

setup_shell_aliases() {
  local user="$1"
  local home rc
  home="$(getent passwd "$user" | cut -d: -f6)"
  rc="${home}/.bashrc"
  [[ -f "$rc" ]] || return

  local marker="# LBG Claude core140"
  if grep -q "$marker" "$rc" 2>/dev/null; then
    log "Alias déjà présents dans ${rc}"
    return
  fi

  log "Alias claude-lbg dans ${rc}…"
  cat >>"$rc" <<EOF

$marker
export LBG_REPO_ROOT="${APP_DIR}"
alias claude-lbg='cd ${APP_DIR} && claude work .'
alias claude-lbg-chat='cd ${APP_DIR} && claude chat'
alias lbg-tmux='tmux attach -t lbg 2>/dev/null || tmux new -s lbg'
EOF
  chown "${user}:${user}" "$rc" 2>/dev/null || true
}

verify_lan() {
  log "Vérification LAN…"
  curl -sf --max-time 5 "http://${CORE_IP}:8000/healthz" >/dev/null \
    && log "  OK backend ${CORE_IP}:8000" \
    || log "  ÉCHEC backend ${CORE_IP}:8000"
  curl -sf --max-time 5 "http://${CORE_IP}:8010/healthz" >/dev/null \
    && log "  OK orchestrateur ${CORE_IP}:8010" \
    || log "  ÉCHEC orchestrateur ${CORE_IP}:8010"
  curl -sf --max-time 5 "http://${FRONT_IP}:11434/" >/dev/null \
    && log "  OK Ollama ${FRONT_IP}:11434" \
    || log "  INFO Ollama ${FRONT_IP}:11434 non joint"
}

print_next_steps() {
  cat <<EOF

=== Prochaines étapes ===

1. Auth Claude (une fois, interactif) :
   sudo -u ${TARGET_USER} -i
   claude login

2. Session persistante (PuTTY / SSH) :
   lbg-tmux
   claude-lbg

3. Build pilot_shell (si besoin) :
   cd ${APP_DIR}/pilot_shell && npm install && npm run build

4. Proxmox (si pas encore fait) — VM 140 :
   RAM  8 → 16 GiB
   Disk 45 → 100+ GiB puis dans la VM : growpart + resize2fs

Doc : docs/fusion_env_lan.md (§ VM 140 — backend + Claude Code)

EOF
}

# --- main ---
warn_host
need_sudo
install_apt_base
install_node
install_claude_for_user "$TARGET_USER"
setup_shell_aliases "$TARGET_USER"
verify_lan
print_next_steps
log "Terminé."
