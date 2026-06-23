#!/usr/bin/env bash
# Connecte / redémarre Lia + Nix (headless) et téléporte Lia au bar cantina (cell 1082877).
# Usage :
#   bash infra/scripts/bring_lia_nix_cantina_vm.sh
#   bash infra/scripts/bring_lia_nix_cantina_vm.sh --reload-lua   # redémarre Prime (déconnecte les joueurs)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
RELOAD_LUA=0
for arg in "$@"; do
  case "$arg" in
    --reload-lua) RELOAD_LUA=1 ;;
  esac
done

echo "=== Lia/Nix → cantina (${VM_USER}@${VM_HOST}) ==="

scp -q "${ROOT_DIR}/content/core3/lua/ia_bridge_screenplay.lua" \
  "${VM_USER}@${VM_HOST}:/tmp/ia_bridge_screenplay.lua"

ssh "${VM_USER}@${VM_HOST}" "RELOAD_LUA=${RELOAD_LUA} BIN='${BIN}' bash -s" <<'EOF'
set -euo pipefail
sudo cp /tmp/ia_bridge_screenplay.lua "${BIN}/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua"

if [[ "${RELOAD_LUA}" == "1" ]]; then
  echo "[1/5] Redémarrage Prime (recharge screenplay + snapshots Teome)..."
  sudo systemctl restart lbg-core3-prime.service
  for i in $(seq 1 60); do
    grep -q "started on port 44563" "${BIN}/log/core3.log" 2>/dev/null && break
    sleep 2
  done
  sleep 8
else
  echo "[1/5] Prime laissé actif (pas de déco joueurs). Utilisez --reload-lua si besoin."
fi

echo "[2/5] Mode mouvement teleport + redémarrage bots..."
echo teleport | sudo tee "${BIN}/ia_bridge/movement_mode" >/dev/null
sudo systemctl restart lbg-core3-ia-bot-client.service
sudo systemctl restart lbg-core3-ia-bot-client-nix.service
sleep 28

echo "[3/5] File cantina (Lia) cote client..."
{
  printf '%s\n' 'housing_enter|Lia|tatooine|0|0|0|cantina'
  printf '%s\n' 'say|Lia|tatooine|0|0|0|Salut — je suis cote client du comptoir, prete a danser.'
} | sudo tee -a "${BIN}/ia_bridge/pending.jsonl" >/dev/null
sleep 8

echo "[4/5] Présence Lia (JSON)..."
sudo tee "${BIN}/ia_bridge/lia_presence.json" >/dev/null <<'JSON'
{
  "mode": "auto",
  "presence": "cantina",
  "cell": 1082877,
  "note": "housing_enter via bring_lia_nix_cantina_vm.sh"
}
JSON

echo "[5/5] État..."
python3 <<PY
import json
from pathlib import Path
bin = Path("${BIN}")
for u in ("lbg-core3-ia-bot-client", "lbg-core3-ia-bot-client-nix"):
    import subprocess
    st = subprocess.check_output(["systemctl", "is-active", u], text=True).strip()
    print(f"  {u}: {st}")
snap = bin / "ia_bridge/player_snapshots.json"
if snap.is_file():
    d = json.loads(snap.read_text())
    for name, p in sorted((d.get("players") or {}).items()):
        on = p.get("online")
        cell = p.get("parent_id")
        print(f"  snapshot {name}: online={on} cell={cell} x={p.get('x')} y={p.get('y')} z={p.get('z')}")
else:
    print("  player_snapshots.json absent")
PY
EOF

echo ""
echo "En jeu (Prime) : Lia face au comptoir (cote client), Nix dehors Mos Eisley."
echo "Godot : relancer F5 — zone: Lia, Nix, Teome (après --reload-lua)."
