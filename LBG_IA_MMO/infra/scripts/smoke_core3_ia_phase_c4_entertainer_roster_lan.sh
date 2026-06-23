#!/usr/bin/env bash
# Smoke C.4 — roster entertainer Bige/Lyra + 5 pilotes sidecar.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke C.4 — Entertainer roster → ${VM_USER}@${VM_HOST} ==="

python3 <<PY
import json
from pathlib import Path
cat = json.loads(Path("${ROOT_DIR}/content/core3/core3_npc_catalog.json").read_text())
rosters = [r for r in cat.get("rosters", []) if r.get("roster_id") == "roster:mos_entertainer_trainer"]
assert rosters and rosters[0].get("status") == "active"
slots = {s["pilot_id"] for s in rosters[0]["slots"]}
assert slots == {"npc:core3_bige_coto", "npc:core3_lyra_velo"}
print("OK catalog roster entertainer")
PY

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
assert d.get(\"npc_pilot_count\") == 5, d
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
ids=[p.get(\"pilot_id\") for p in pl.get(\"pilots\") or []]
for pid in (\"npc:core3_bige_coto\", \"npc:core3_lyra_velo\"):
    assert pid in ids, ids
h=int(__import__(\"datetime\").datetime.now(__import__(\"zoneinfo\").ZoneInfo(\"Europe/Paris\")).strftime(\"%H\"))
on=[p for p in pl[\"pilots\"] if p.get(\"online\")]
print(\"OK pilots=5 local_hour=\", h, \"online=\", [(p[\"pilot_id\"], p.get(\"online\")) for p in on if p[\"pilot_id\"].startswith(\"npc:core3_\")])
"'

echo "=== Smoke C.4 OK ==="
