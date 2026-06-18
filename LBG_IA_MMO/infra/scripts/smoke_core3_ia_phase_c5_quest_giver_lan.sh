#!/usr/bin/env bash
# Smoke C.5 — triplon donneur de quete Mos Eisley.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
WITH_THINK=0
for arg in "$@"; do
  case "$arg" in
    --with-think) WITH_THINK=1 ;;
  esac
done

echo "=== Smoke C.5 — quest giver → ${VM_USER}@${VM_HOST} ==="

python3 <<PY
import json
import time
from pathlib import Path

cat = json.loads(Path("${ROOT_DIR}/content/core3/core3_npc_catalog.json").read_text())
roster = next(r for r in cat["rosters"] if r.get("roster_id") == "roster:mos_eisley_quest_giver")
assert roster.get("status") == "active", roster.get("status")
slots = roster["slots"]
assert len(slots) == 3, len(slots)
for pid in ("npc:core3_vex_sorn", "npc:core3_nira_kell", "npc:core3_daan_oth"):
    assert any(s["pilot_id"] == pid for s in slots), pid
prof = cat["profiles"]["profile:quest_giver_mos_v1"]
assert "offer_quest" in prof.get("actions_allowed", []), prof
print("OK catalog roster + offer_quest profile")
PY

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
assert d.get(\"ok\"), d
assert int(d.get(\"npc_pilot_count\") or 0) >= 9, d
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
ids={p[\"pilot_id\"] for p in pl[\"pilots\"]}
for pid in (\"npc:core3_vex_sorn\", \"npc:core3_nira_kell\", \"npc:core3_daan_oth\"):
    assert pid in ids, sorted(ids)[:12]
on=[p for p in pl[\"pilots\"] if p[\"pilot_id\"] in (\"npc:core3_vex_sorn\",\"npc:core3_nira_kell\",\"npc:core3_daan_oth\") and p.get(\"online\")]
print(\"OK pilots>=9 quest_roster_online=\", [(p[\"pilot_id\"], p.get(\"display_name\")) for p in on])
assert len(on) <= 2, on
"'

if [[ "${WITH_THINK}" == "1" ]]; then
  curl -sf -X POST "http://${VM_HOST}:8791/v1/npc-think" \
    -H 'Content-Type: application/json' \
    -d '{"pilot_id":"npc:core3_vex_sorn","prompt":"Un voyageur demande du travail sur Tatooine.","enqueue":true}' \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d); assert d.get('ok') or d.get('enqueued')"
  echo "OK npc-think (verifier spatial chat IG si Lia online)"
fi

echo "=== Smoke C.5 OK ==="
