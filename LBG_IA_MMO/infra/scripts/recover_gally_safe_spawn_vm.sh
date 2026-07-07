#!/usr/bin/env bash
# Sort Gally de Mos Eisley (zone >1000 objets custom → SEGV + blocage client).
# Téléporte offline vers cantina ME (intérieur, peu d'objets monde).
#
# Usage : bash infra/scripts/recover_gally_safe_spawn_vm.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
GALLY_OID="${GALLY_CHARACTER_OID:-281474993555798}"
# Dernière position connue (online-players.log)
OLD_X="${GALLY_OLD_X:-3526}"
OLD_Y="${GALLY_OLD_Y:--4801}"
OLD_Z="${GALLY_OLD_Z:-0}"
# Hors rayon 1000 m Mos Eisley (évite >1000 objets custom)
NEW_X="${GALLY_NEW_X:-5000}"
NEW_Z="${GALLY_NEW_Z:-5}"
NEW_Y="${GALLY_NEW_Y:--4800}"

echo "=== Recovery Gally safe spawn → ${VM_USER}@${VM_HOST} ==="

scp -q "${ROOT_DIR}/tools/core3_relocate_player_bdb.py" \
  "${VM_USER}@${VM_HOST}:/tmp/core3_relocate_player_bdb.py"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
BIN="${BIN}"
GALLY_OID="${GALLY_OID}"

echo "[1/6] Arrêt bots IA + Prime..."
for u in lbg-core3-ia-bot-client lbg-core3-ia-bot-client-nix lbg-core3-ia-bots-ensure; do
  sudo systemctl stop "\$u" 2>/dev/null || true
done
pkill -x core3client 2>/dev/null || true
sudo systemctl stop lbg-core3-prime.service
for _ in \$(seq 1 30); do
  pgrep -x core3-clean >/dev/null || break
  sleep 1
done
if pgrep -x core3-clean >/dev/null; then
  echo "ERROR: core3-clean encore actif" >&2
  exit 1
fi

echo "[2/6] berkeleydb (pip user)..."
python3 -c "import berkeleydb" 2>/dev/null || pip3 install --user berkeleydb -q

echo "[3/6] Patch position Gally (OID=\${GALLY_OID})..."
python3 /tmp/core3_relocate_player_bdb.py \\
  --db "\${BIN}/databases/sceneobjects.db" \\
  --oid "\${GALLY_OID}" \\
  --old-x ${OLD_X} --old-z ${OLD_Z} --old-y ${OLD_Y} \\
  --new-x ${NEW_X} --new-z ${NEW_Z} --new-y ${NEW_Y}

echo "[4/6] Désactivation auto-reconnect bots au boot (temporaire)..."
sudo mkdir -p /etc/systemd/system/lbg-core3-prime.service.d
if [[ ! -f /etc/systemd/system/lbg-core3-prime.service.d/skip-ia-bots.conf ]]; then
  sudo tee /etc/systemd/system/lbg-core3-prime.service.d/skip-ia-bots.conf >/dev/null <<'DROPIN'
[Service]
ExecStartPost=
DROPIN
  sudo systemctl daemon-reload
fi

echo "[5/6] Redémarrage Prime (sans bots)..."
sudo systemctl start lbg-core3-prime.service
for i in \$(seq 1 90); do
  grep -q "started on port 44563" "\${BIN}/log/core3.log" 2>/dev/null && break
  sleep 2
done
sleep 5

echo "[6/6] Ports..."
ss -ulnp | grep -E '44553|44563' || echo "WARN: ports pas encore up — attendre ~2 min"

echo ""
echo "OK — Gally déplacé hors zone ME (${NEW_X}, ${NEW_Y}). Bots IA désactivés au boot."
echo "Relance client Prime, attendre fin chargement."
echo "Pour réactiver bots : sudo rm /etc/systemd/system/lbg-core3-prime.service.d/skip-ia-bots.conf && sudo systemctl daemon-reload"
EOF
