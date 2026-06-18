#!/usr/bin/env bash
# Smoke C.4b — game_time + triplon entertainer (3 slots).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke C.4b — temps jeu → ${VM_USER}@${VM_HOST} ==="

python3 <<PY
import json
import time
from pathlib import Path

cat = json.loads(Path("${ROOT_DIR}/content/core3/core3_npc_catalog.json").read_text())
gt = cat.get("game_time") or {}
assert gt.get("real_hours_per_game_day") == 6, gt
assert gt.get("game_days_per_real_day") == 4, gt
ph = gt.get("phase_hours_real") or {}
assert ph.get("work") == 2 and ph.get("rest") == 2 and ph.get("leisure") == 2

roster = next(r for r in cat["rosters"] if r.get("roster_id") == "roster:mos_entertainer_trainer")
slots = roster["slots"]
assert len(slots) == 3, len(slots)
offsets = {s["pilot_id"]: s["shift_offset"] for s in slots}
assert offsets["npc:core3_bige_coto"] == 0
assert offsets["npc:core3_lyra_velo"] == 1
assert offsets["npc:core3_talen_ress"] == 2
print("OK catalog game_time + triplon offsets")


def lifecycle_phase(shift_offset: int) -> str:
    day_sec = 6 * 3600
    work_sec = 2 * 3600
    rest_sec = 2 * 3600
    in_day = int(time.time()) % day_sec
    off = shift_offset % 3
    if in_day < work_sec:
        idx = (0 + off) % 3
    elif in_day < work_sec + rest_sec:
        idx = (1 + off) % 3
    else:
        idx = (2 + off) % 3
    return ("work", "rest", "leisure")[idx]


for pid, off in offsets.items():
    print(f"  phase now {pid} offset={off} -> {lifecycle_phase(off)}")
print("OK lifecycle calculator")
PY

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, time, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
cnt = int(d.get(\"npc_pilot_count\") or 0)
assert cnt >= 6, d
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
ids=[p[\"pilot_id\"] for p in pl[\"pilots\"]]
for pid in (\"npc:core3_bige_coto\", \"npc:core3_lyra_velo\", \"npc:core3_talen_ress\"):
    assert pid in ids, ids
on=[p for p in pl[\"pilots\"] if p.get(\"online\") and \"entertainer\" in p.get(\"lbg_npc_id\", \"\") or p[\"pilot_id\"].startswith(\"npc:core3_\") and p[\"pilot_id\"] in (\"npc:core3_bige_coto\",\"npc:core3_lyra_velo\",\"npc:core3_talen_ress\")]
roster_on=[p for p in pl[\"pilots\"] if p[\"pilot_id\"] in (\"npc:core3_bige_coto\",\"npc:core3_lyra_velo\",\"npc:core3_talen_ress\") and p.get(\"online\")]
print(\"OK pilots=\", cnt, \"roster_online=\", [(p[\"pilot_id\"], p.get(\"display_name\")) for p in roster_on])
assert len(roster_on) <= 2, roster_on
"'

echo "=== Smoke C.4b OK ==="
