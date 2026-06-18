#!/usr/bin/env bash
# Smoke consolidé — systèmes monde Prime (catalogues JSON + bridge + pending optionnel).
#
# Usage :
#   bash infra/scripts/smoke_core3_prime_world_lan.sh
#   bash infra/scripts/smoke_core3_prime_world_lan.sh --with-think
#   bash infra/scripts/smoke_core3_prime_world_lan.sh --demo-pending

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WITH_THINK=0
DEMO_PENDING=0

for arg in "$@"; do
  case "$arg" in
    --with-think) WITH_THINK=1 ;;
    --demo-pending) DEMO_PENDING=1 ;;
  esac
done

echo "=== Smoke Prime World (catalogues locaux) ==="
python3 <<PY
import json
from pathlib import Path

base = Path("${ROOT_DIR}/content/core3")
files = [
    "core3_npc_catalog.json",
    "core3_quest_templates.json",
    "core3_economy.json",
    "core3_factions.json",
    "core3_planet_rules.json",
    "core3_npc_simulation.json",
]
for name in files:
    p = base / name
    assert p.is_file(), p
    json.loads(p.read_text())
    print("OK", name)

cat = json.loads((base / "core3_npc_catalog.json").read_text())
assert cat.get("game_time", {}).get("real_hours_per_game_day") == 6
quests = json.loads((base / "core3_quest_templates.json").read_text())
assert len(quests.get("templates", [])) >= 3
econ = json.loads((base / "core3_economy.json").read_text())
assert len(econ.get("shops", [])) >= 2
print("OK structure MVP (game_time, 3 quêtes, 2 shops)")
PY

echo ""
echo "=== Smokes bridge historiques (VM) ==="
bash "${ROOT_DIR}/infra/scripts/smoke_core3_ia_phase_c4b_game_time_lan.sh"
bash "${ROOT_DIR}/infra/scripts/smoke_core3_ia_phase_c5_quest_giver_lan.sh"

if [[ "${WITH_THINK}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/smoke_core3_ia_phase_b_lan.sh" --with-think || true
  bash "${ROOT_DIR}/infra/scripts/smoke_core3_ia_phase_c_lan.sh" --with-think || true
fi

if [[ "${DEMO_PENDING}" == "1" ]]; then
  echo ""
  bash "${ROOT_DIR}/infra/scripts/demo_core3_prime_pending_vm.sh"
fi

echo ""
echo "=== Smoke Prime World terminé ==="
echo "Doc : ${ROOT_DIR}/docs/core3_prime_runbook.md"
