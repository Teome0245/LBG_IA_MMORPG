#!/usr/bin/env bash
# Installe logrotate + limites journald pour Core3 / pont IA sur une VM.
# Usage :
#   LBG_TARGET_VM_HOST=192.168.0.246 bash infra/scripts/install_core3_logrotate_vm.sh prime
#   LBG_TARGET_VM_HOST=192.168.0.245 bash infra/scripts/install_core3_logrotate_vm.sh precu

set -euo pipefail

ROLE="${1:-prime}"
VM_HOST="${LBG_TARGET_VM_HOST:-$(
  case "${ROLE}" in
    prime) echo "192.168.0.246" ;;
    precu) echo "192.168.0.245" ;;
    *) echo "192.168.0.246" ;;
  esac
)}"
VM_USER="${LBG_VM_USER:-lbg}"

TMP_LOG="/tmp/core3-clean.log"
BIN_LOG_DIR="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/log"
IA_BRIDGE_DIR="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge"

case "${ROLE}" in
  precu)
    TMP_LOG="/tmp/core3-swgemu.log"
    BIN_LOG_DIR="/opt/lbg-new-mmo/MMOCoreORB/bin/log"
    IA_BRIDGE_DIR=""
    ;;
esac

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
ROLE="${ROLE}"
TMP_LOG="${TMP_LOG}"
BIN_LOG_DIR="${BIN_LOG_DIR}"
IA_BRIDGE_DIR="${IA_BRIDGE_DIR}"

sudo tee /etc/logrotate.d/lbg-core3-\${ROLE} >/dev/null <<ROT
# Journal systemd Prime/PreCU — redirection bash (copytruncate = pas de reload)
\${TMP_LOG} {
    daily
    rotate 3
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 50M
}

# Logs internes Core3 (core3.log, lua.log, …)
\${BIN_LOG_DIR}/*.log {
    daily
    rotate 3
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 30M
}

\${BIN_LOG_DIR}/zArchive/*.log {
    weekly
    rotate 2
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 40M
}
ROT

if [[ -n "\${IA_BRIDGE_DIR}" && -d "\${IA_BRIDGE_DIR}" ]]; then
  sudo tee /etc/logrotate.d/lbg-ia-bridge-\${ROLE} >/dev/null <<ROT
# Pont IA — jsonl volumineux (events, bot_move, …)
\${IA_BRIDGE_DIR}/*.jsonl {
    daily
    rotate 2
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 15M
}

\${IA_BRIDGE_DIR}/catalog_boot.log {
    weekly
    rotate 2
    compress
    missingok
    notifempty
    copytruncate
    maxsize 5M
}
ROT
fi

sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/lbg-limits.conf >/dev/null <<'JOURNAL'
[Journal]
SystemMaxUse=80M
SystemKeepFree=500M
MaxRetentionSec=7day
JOURNAL
sudo systemctl restart systemd-journald 2>/dev/null || true

sudo logrotate -f /etc/logrotate.d/lbg-core3-\${ROLE} 2>/dev/null || true
[[ -f /etc/logrotate.d/lbg-ia-bridge-\${ROLE} ]] && sudo logrotate -f /etc/logrotate.d/lbg-ia-bridge-\${ROLE} 2>/dev/null || true

echo "OK logrotate \${ROLE} sur ${VM_HOST}"
echo "  tmp: \${TMP_LOG} (max 50M x3)"
echo "  bin: \${BIN_LOG_DIR}/*.log (max 30M x3)"
if [[ -n "\${IA_BRIDGE_DIR}" ]]; then
  echo "  ia_bridge: \${IA_BRIDGE_DIR}/*.jsonl (max 15M x2)"
fi
sudo journalctl --disk-usage 2>/dev/null || true
df -h / | tail -1
EOF
