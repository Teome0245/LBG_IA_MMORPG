#!/usr/bin/env bash
# Vide / limite les journaux Core3 volumineux (sans redémarrer si --no-restart).
#
# Usage :
#   bash infra/scripts/truncate_core3_logs_vm.sh prime
#   bash infra/scripts/truncate_core3_logs_vm.sh precu
#   bash infra/scripts/truncate_core3_logs_vm.sh both
#   bash infra/scripts/truncate_core3_logs_vm.sh prime --restart
#   bash infra/scripts/truncate_core3_logs_vm.sh prime --install-logrotate

set -euo pipefail

ROLE="${1:-both}"
DO_RESTART=0
INSTALL_LOGROTATE=0
shift || true
for arg in "$@"; do
  case "$arg" in
    --restart) DO_RESTART=1 ;;
    --install-logrotate) INSTALL_LOGROTATE=1 ;;
  esac
done

VM_USER="${LBG_VM_USER:-lbg}"
PRIME_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"
PRECU_HOST="${LBG_PRECU_VM_HOST:-192.168.0.245}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_truncate_prime() {
  local host="$1" restart="$2"
  ssh "${VM_USER}@${host}" "RESTART=${restart}" bash -s <<'EOF'
set -euo pipefail
TMP_LOG="/tmp/core3-clean.log"
BIN_LOG_DIR="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/log"
IA_BRIDGE_DIR="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge"

_trim_file() {
  local f="$1" max_mb="${2:-20}"
  if [[ -f "$f" ]]; then
    local sz
    sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
    if (( sz > max_mb * 1024 * 1024 )); then
      :> "$f"
      echo "  truncated ${f} (was $(( sz / 1024 / 1024 ))M)"
    fi
  fi
}

:> "$TMP_LOG" 2>/dev/null || sudo truncate -s 0 "$TMP_LOG" 2>/dev/null || true

if [[ -d "$BIN_LOG_DIR" ]]; then
  find "$BIN_LOG_DIR" -maxdepth 1 -type f -name '*.log' -size +20M -exec truncate -s 0 {} + 2>/dev/null || true
  if [[ -d "$BIN_LOG_DIR/zArchive" ]]; then
    find "$BIN_LOG_DIR/zArchive" -type f -name '*.log' -mtime +3 -delete 2>/dev/null || true
    find "$BIN_LOG_DIR/zArchive" -type f -name '*.log' -size +30M -exec truncate -s 0 {} + 2>/dev/null || true
  fi
fi

if [[ -d "$IA_BRIDGE_DIR" ]]; then
  for j in events.jsonl world_events.jsonl bot_move.jsonl; do
    _trim_file "${IA_BRIDGE_DIR}/${j}" 15
  done
  for f in "${IA_BRIDGE_DIR}"/pending.jsonl.stale_*; do
    [[ -f "$f" ]] && _trim_file "$f" 15
  done
  _trim_file "${IA_BRIDGE_DIR}/catalog_boot.log" 5
  find "$IA_BRIDGE_DIR" -maxdepth 1 -name 'pending.jsonl.stale_*' -mtime +7 -delete 2>/dev/null || true
fi

sudo journalctl --vacuum-size=50M 2>/dev/null || true

if [[ "${RESTART:-0}" == "1" ]]; then
  sudo systemctl restart lbg-core3-prime.service 2>/dev/null || true
fi
echo "OK truncate Prime logs"
df -h / | tail -1
du -sh "$BIN_LOG_DIR" "$IA_BRIDGE_DIR" "$TMP_LOG" 2>/dev/null || true
EOF
}

_truncate_precu() {
  local host="$1" restart="$2"
  ssh "${VM_USER}@${host}" "RESTART=${restart}" bash -s <<'EOF'
set -euo pipefail
TMP_LOG="/tmp/core3-swgemu.log"
BIN_LOG_DIR="/opt/lbg-new-mmo/MMOCoreORB/bin/log"

:> "$TMP_LOG" 2>/dev/null || sudo truncate -s 0 "$TMP_LOG" 2>/dev/null || true
if [[ -d "$BIN_LOG_DIR" ]]; then
  find "$BIN_LOG_DIR" -maxdepth 1 -type f -name '*.log' -size +20M -exec truncate -s 0 {} + 2>/dev/null || true
fi
sudo journalctl --vacuum-size=50M 2>/dev/null || true
if [[ "${RESTART:-0}" == "1" ]]; then
  sudo systemctl restart lbg-core3-precu.service 2>/dev/null || true
fi
echo "OK truncate PreCU logs"
df -h / | tail -1
EOF
}

R_FLAG="${DO_RESTART}"
case "${ROLE}" in
  prime) _truncate_prime "${PRIME_HOST}" "${R_FLAG}" ;;
  precu) _truncate_precu "${PRECU_HOST}" "${R_FLAG}" ;;
  both)
    _truncate_prime "${PRIME_HOST}" "${R_FLAG}"
    _truncate_precu "${PRECU_HOST}" "${R_FLAG}"
    ;;
  *) echo "Usage: $0 {prime|precu|both} [--restart] [--install-logrotate]" >&2; exit 1 ;;
esac

if [[ "${INSTALL_LOGROTATE}" == "1" ]]; then
  case "${ROLE}" in
    prime) LBG_TARGET_VM_HOST="${PRIME_HOST}" bash "${SCRIPT_DIR}/install_core3_logrotate_vm.sh" prime ;;
    precu) LBG_TARGET_VM_HOST="${PRECU_HOST}" bash "${SCRIPT_DIR}/install_core3_logrotate_vm.sh" precu ;;
    both)
      LBG_TARGET_VM_HOST="${PRIME_HOST}" bash "${SCRIPT_DIR}/install_core3_logrotate_vm.sh" prime
      LBG_TARGET_VM_HOST="${PRECU_HOST}" bash "${SCRIPT_DIR}/install_core3_logrotate_vm.sh" precu
      ;;
  esac
fi
