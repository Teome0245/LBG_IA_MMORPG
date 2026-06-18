#!/usr/bin/env bash
# Remet Lia/Nix visibles pour les joueurs : purge fantomes + restart bots + cantina Lia.
# Usage : bash infra/scripts/recover_ia_bots_visible_vm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

echo "=== Recovery bots visibles → ${VM_USER}@${VM_HOST} ==="

scp -q "${ROOT_DIR}/infra/scripts/run_core3_ia_bot_client_vm.sh" \
  "${VM_USER}@${VM_HOST}:/tmp/run_core3_ia_bot_client_vm.sh"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail
sudo cp /tmp/run_core3_ia_bot_client_vm.sh /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
sudo chmod +x /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh

echo "teleport" | sudo tee ${BIN}/ia_bridge/movement_mode >/dev/null

for u in lbg-core3-ia-bot-client lbg-core3-ia-bot-client-nix; do
  sudo systemctl stop "\$u" 2>/dev/null || true
done
pkill -x core3client 2>/dev/null || true
sleep 3

echo "Redemarrage Prime (purge sessions fantomes)..."
sudo systemctl restart lbg-core3-prime.service
sleep 12

sudo systemctl start lbg-core3-ia-bot-client.service
sudo systemctl start lbg-core3-ia-bot-client-nix.service
sleep 25

printf '%s\n' 'housing_enter|Lia|tatooine|0|0|0|cantina' >> ${BIN}/ia_bridge/pending.jsonl
sleep 6

python3 <<'PY'
import json
from pathlib import Path
who = Path("${BIN}/log/who.json")
if who.is_file():
    d = json.loads(who.read_text())
    print("Joueurs connectes (who.json):")
    for c in d.get("clients") or []:
        print(
            " -",
            c.get("firstName"),
            "session",
            c.get("sessionSeconds"),
            "pos",
            round(c.get("worldPositionX", 0), 1),
            round(c.get("worldPositionY", 0), 1),
        )
else:
    print("who.json absent")
snap = Path("${BIN}/ia_bridge/player_snapshots.json")
if snap.is_file():
    d = json.loads(snap.read_text())
    for name, p in (d.get("players") or {}).items():
        print(f"snapshot {name}: parent={p.get('parent_id')} x={p.get('x')} y={p.get('y')}")
PY
EOF

echo ""
echo "Verifie en jeu : Serveur Prime (port 44563), pas PreCu."
echo "Nix attendu dehors ~3468, -4787 | Lia en cantina Mos Eisley."
