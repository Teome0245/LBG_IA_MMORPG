#!/usr/bin/env bash
# Installe et active lbg-core3-prime.service sur la VM MMO (245).
# Remplace les redémarrages manuels pkill + nohup (redémarrage auto en cas de crash).
#
# Usage :
#   bash infra/scripts/install_core3_prime_systemd_vm.sh
#   bash infra/scripts/install_core3_prime_systemd_vm.sh --no-start   # install sans démarrer

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
DO_START=1
for arg in "$@"; do
  case "$arg" in
    --no-start) DO_START=0 ;;
  esac
done

echo "=== Install systemd lbg-core3-prime → ${VM_USER}@${VM_HOST} ==="

# PreCu arrêté (cohérent avec Prime seul)
bash "${ROOT_DIR}/infra/scripts/stop_core3_precu_vm.sh"

scp -q "${ROOT_DIR}/infra/systemd/lbg-core3-prime.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-prime.service"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
DO_START=${DO_START}

# Arrêt instance nohup orpheline avant bascule systemd
pkill -x core3-clean 2>/dev/null || true
sleep 2

sudo cp /tmp/lbg-core3-prime.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-prime.service

if [[ "\${DO_START}" == "1" ]]; then
  sudo systemctl restart lbg-core3-prime.service
  sleep 2
  systemctl show lbg-core3-prime.service -p ActiveState,SubState,MainPID --no-pager
  state=\$(systemctl show lbg-core3-prime.service -p ActiveState --value)
  if [[ "\${state}" != "active" && "\${state}" != "activating" ]]; then
    echo "ERROR: lbg-core3-prime.service etat inattendu: \${state}" >&2
    journalctl -u lbg-core3-prime.service -n 20 --no-pager >&2 || true
    exit 1
  fi
  pgrep -a core3-clean || { echo "ERROR: core3-clean absent" >&2; exit 1; }
else
  echo "Unité installée (pas de start — --no-start)"
fi
EOF

echo ""
echo "OK — Prime géré par systemd (Restart=always, log /tmp/core3-clean.log)"
echo "  status : ssh ${VM_USER}@${VM_HOST} 'systemctl status lbg-core3-prime.service'"
echo "  restart: bash infra/scripts/restart_core3_prime_vm.sh"
echo "  launchpad : http://${VM_HOST}:8792/ (ready ~2–3 min après start)"
