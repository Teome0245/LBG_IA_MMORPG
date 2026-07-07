#!/usr/bin/env bash
# Installe le miroir M3 en service systemd (boucle continue, redémarrage auto).
#
# Usage local WSL (recommandé si Godot sur le même PC Windows) :
#   bash infra/scripts/install_m3_mirror_systemd.sh --user
#
# Usage VM core 140 (Godot sur un autre PC — définir GODOT_HOST dans m3_mirror.env) :
#   bash infra/scripts/install_m3_mirror_systemd.sh --vm 192.168.0.140
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="user"
VM_HOST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) MODE="user" ;;
    --vm) MODE="vm"; VM_HOST="${2:?IP VM requise}"; shift ;;
    *) echo "Usage: $0 [--user | --vm IP]" >&2; exit 1 ;;
  esac
  shift
done

chmod +x "${ROOT}/tools/zone_observer/run_m3_mirror_daemon.sh"

ENV_EXAMPLE="${ROOT}/infra/config/m3_mirror.env.example"
ENV_FILE="${ROOT}/infra/config/m3_mirror.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Créé ${ENV_FILE} — édite GODOT_HOST si besoin (VM 140 → IP du PC Windows)"
fi

if [[ "${MODE}" == "user" ]]; then
  UNIT_SRC="${ROOT}/infra/systemd/lbg-m3-mirror-user.service"
  UNIT_DST="${HOME}/.config/systemd/user/lbg-m3-mirror.service"
  mkdir -p "${HOME}/.config/systemd/user"
  sed "s|%h|${HOME}|g" "${UNIT_SRC}" > "${UNIT_DST}"
  systemctl --user daemon-reload
  systemctl --user enable lbg-m3-mirror.service
  systemctl --user restart lbg-m3-mirror.service
  systemctl --user --no-pager status lbg-m3-mirror.service || true
  echo ""
  echo "OK — miroir user actif. Logs : journalctl --user -u lbg-m3-mirror -f"
  echo "Godot doit écouter UDP :${GODOT_PORT:-12345}"
  exit 0
fi

echo "=== Déploiement miroir M3 sur ${VM_HOST} ==="
rsync -avz \
  "${ROOT}/tools/zone_observer/" \
  "${ROOT}/infra/config/m3_mirror.env" \
  "${ROOT}/infra/systemd/lbg-m3-mirror.service" \
  "lbg@${VM_HOST}:/tmp/m3_mirror_deploy/"

ssh "lbg@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo mkdir -p /opt/LBG_IA_MMO/tools/zone_observer /opt/LBG_IA_MMO/infra/config
sudo cp -a /tmp/m3_mirror_deploy/zone_feed.py /tmp/m3_mirror_deploy/godot_bridge.py \
  /tmp/m3_mirror_deploy/run_m3_mirror_daemon.sh /tmp/m3_mirror_deploy/run_m3_mirror.sh \
  /opt/LBG_IA_MMO/tools/zone_observer/ 2>/dev/null || true
sudo cp -a /tmp/m3_mirror_deploy/*.py /opt/LBG_IA_MMO/tools/zone_observer/ 2>/dev/null || true
sudo cp /tmp/m3_mirror_deploy/m3_mirror.env /opt/LBG_IA_MMO/infra/config/m3_mirror.env
sudo cp /tmp/m3_mirror_deploy/lbg-m3-mirror.service /etc/systemd/system/lbg-m3-mirror.service
sudo chmod +x /opt/LBG_IA_MMO/tools/zone_observer/run_m3_mirror_daemon.sh
sudo systemctl daemon-reload
sudo systemctl enable lbg-m3-mirror.service
sudo systemctl restart lbg-m3-mirror.service
systemctl is-active lbg-m3-mirror.service
EOF

echo "OK — VM ${VM_HOST} : journalctl -u lbg-m3-mirror -f"
echo "IMPORTANT : GODOT_HOST dans /opt/LBG_IA_MMO/infra/config/m3_mirror.env = IP LAN du PC Windows"
