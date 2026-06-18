#!/usr/bin/env bash
# Applique un layout Scrapaltai exporté dans MOD_LBG → screenplay + hub JSON repo.
set -euo pipefail

MOD_LBG="${MOD_LBG_ROOT:-/mnt/j/swgemu/MOD_LBG}"
LAYOUT="${1:-$MOD_LBG/scrapaltai_v7_default.json}"
BUMP="${2:-8}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "$LAYOUT" ]]; then
  echo "Layout introuvable: $LAYOUT" >&2
  echo "Exportez depuis l'éditeur vers J:\\swgemu\\MOD_LBG\\ puis relancez." >&2
  exit 1
fi

echo "Apply: $LAYOUT (bump v$BUMP)"
python3 "$REPO_ROOT/tools/world_editor/apply_scrapaltai_layout.py" \
  "$LAYOUT" \
  --bump-version "$BUMP"

echo "OK — déployer: bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart"
echo "IG: lbg_we hub clean → lbg_we hub build"
