#!/usr/bin/env bash
# Smoke C.3 — Kisreudi Teste (scientifique poste fixe).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke C.3 — Kisreudi → ${VM_USER}@${VM_HOST} ==="

python3 <<PY
import json
from pathlib import Path
cat = json.loads(Path("${ROOT_DIR}/content/core3/core3_npc_catalog.json").read_text())
entries = [e for e in cat["entries"] if e.get("status") == "active"]
assert any(e["pilot_id"] == "npc:core3_kisreudi" for e in entries)
rep = [r for r in cat.get("vanilla_replacements", []) if r.get("status") == "active"]
assert len(rep) >= 1
print("OK catalog kisreudi + vanilla_replacement")
PY

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
assert d.get(\"npc_pilot_count\") == 3, d
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
ids=[p.get(\"pilot_id\") for p in pl.get(\"pilots\") or []]
assert \"npc:core3_kisreudi\" in ids, ids
k=next(p for p in pl[\"pilots\"] if p[\"pilot_id\"]==\"npc:core3_kisreudi\")
print(\"OK pilots=3 kisreudi online=\", k.get(\"online\"), \"name=\", k.get(\"display_name\"))
sn=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-snapshot?npc_id=npc:scientist_mos\"))
assert sn.get(\"ok\"), sn
print(\"OK snapshot scientist_mos\", sn[\"snapshot\"].get(\"x\"), sn[\"snapshot\"].get(\"y\"))
"'

echo "=== Smoke C.3 OK (redemarrer core3-clean si kisreudi absent en jeu) ==="
