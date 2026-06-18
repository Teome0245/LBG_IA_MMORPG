#!/usr/bin/env bash
# Smoke C.3 — Bige Coto (instructeur Entertainer, poste fixe Mos Eisley).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke C.3 — Bige Coto → ${VM_USER}@${VM_HOST} ==="

python3 <<PY
import json
from pathlib import Path
cat = json.loads(Path("${ROOT_DIR}/content/core3/core3_npc_catalog.json").read_text())
assert any(e["pilot_id"] == "npc:core3_bige_coto" for e in cat["entries"] if e.get("status") == "active")
rep = [r for r in cat.get("vanilla_replacements", []) if r.get("replaced_by_entry") == "npc:core3_bige_coto"]
assert rep, "vanilla_replacement manquant"
print("OK catalog bige + vanilla_replacement")
PY

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
assert d.get(\"npc_pilot_count\") == 4, d
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
ids=[p.get(\"pilot_id\") for p in pl.get(\"pilots\") or []]
assert \"npc:core3_bige_coto\" in ids, ids
b=next(p for p in pl[\"pilots\"] if p[\"pilot_id\"]==\"npc:core3_bige_coto\")
print(\"OK pilots=4 bige online=\", b.get(\"online\"), \"name=\", b.get(\"display_name\"))
sn=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-snapshot?npc_id=npc:entertainer_trainer_mos\"))
assert sn.get(\"ok\"), sn
s=sn[\"snapshot\"]
print(\"OK snapshot entertainer_trainer_mos\", s.get(\"x\"), s.get(\"y\"))
"'

echo "=== Smoke C.3 Bige OK (despawn trainer vanilla si doublon IG) ==="
