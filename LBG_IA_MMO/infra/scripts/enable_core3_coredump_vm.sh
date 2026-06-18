#!/usr/bin/env bash
# Active les core dumps systemd pour core3 (post-mortem ABRT/SEGV).
#
# Usage :
#   bash infra/scripts/enable_core3_coredump_vm.sh prime    # VM 246
#   bash infra/scripts/enable_core3_coredump_vm.sh precu    # VM 245
#   bash infra/scripts/enable_core3_coredump_vm.sh both

set -euo pipefail

ROLE="${1:-both}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

_enable() {
  local role="$1" host="$2" unit="$3" bin="$4"
  echo "=== Core dumps ${role} → ${VM_USER}@${host} (${unit}) ==="
  ssh "${VM_USER}@${host}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p /etc/systemd/coredump.conf.d
sudo tee /etc/systemd/coredump.conf.d/lbg-core3.conf >/dev/null <<'CORE'
[Coredump]
Storage=external
Compress=yes
ProcessSizeMax=8G
ExternalSizeMax=8G
MaxUse=4G
CORE
sudo mkdir -p /etc/systemd/system/${unit}.service.d
sudo tee /etc/systemd/system/${unit}.service.d/coredump.conf >/dev/null <<'UNIT'
[Service]
LimitCORE=infinity
UNIT
sudo systemctl daemon-reload
echo "OK: LimitCORE sur ${unit} — analyser : coredumpctl info ${bin}"
EOF
}

case "${ROLE}" in
  prime) _enable prime "${LBG_PRIME_VM_HOST:-192.168.0.246}" lbg-core3-prime core3-clean ;;
  precu) _enable precu "${LBG_PRECU_VM_HOST:-192.168.0.245}" lbg-core3-precu core3-swgemu ;;
  both)
    _enable prime "${LBG_PRIME_VM_HOST:-192.168.0.246}" lbg-core3-prime core3-clean
    _enable precu "${LBG_PRECU_VM_HOST:-192.168.0.245}" lbg-core3-precu core3-swgemu
    ;;
  *) echo "Usage: $0 {prime|precu|both}" >&2; exit 1 ;;
esac

echo "Termine."
