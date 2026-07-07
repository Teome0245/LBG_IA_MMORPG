#!/usr/bin/env bash
# M8 — Déploie scrapaltai_world + rappels post-déploiement
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VM="${LBG_VM_HOST:-lbg@192.168.0.246}"
REMOTE="${LBG_REMOTE_ROOT:-/opt/LBG_IA_MMO}"

echo "=== M8 Scrapaltai / Lost Heaven ==="
echo "Repo: $ROOT"
echo "VM:   $VM:$REMOTE"

if [[ "${1:-}" == "--local-only" ]]; then
  echo "Mode local-only — fichiers prêts dans content/core3/"
  exit 0
fi

rsync -avz \
  "$ROOT/content/core3/scrapaltai_world.json" \
  "$ROOT/content/core3/lua/lbg_scrapaltai_world_screenplay.lua" \
  "$ROOT/content/core3/lua/ia_bridge_screenplay.lua" \
  "$ROOT/content/core3/lua/lbg_lost_heaven_screenplay.lua" \
  "$ROOT/content/core3/lua/lbg_player_hooks.lua" \
  "$ROOT/content/core3/lua/screenplays.lua" \
  "$ROOT/content/core3/core3_npc_pilots.json" \
  "$ROOT/content/core3/core3_planet_rules.json" \
  "$ROOT/content/core3/world_poi/scrapaltai.json" \
  "$VM:$REMOTE/content/core3/"

rsync -avz "$ROOT/content/core3/lua/" "$VM:$REMOTE/content/core3/lua/"

echo ""
echo "Sur la VM, exécuter :"
echo "  bash $REMOTE/infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
echo "  bash $REMOTE/infra/scripts/rebuild_lost_heaven_vm.sh"
echo ""
echo "Client retail : python3 tools/client_patch/patch_starting_locations.py <starting_locations.iff>"
echo "Client Godot  : python3 tools/map_export/export_tatooine_for_godot.py"
