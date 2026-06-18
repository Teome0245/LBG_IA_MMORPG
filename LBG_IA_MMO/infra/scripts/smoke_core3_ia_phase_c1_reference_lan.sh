#!/usr/bin/env bash
# Smoke C.1 — validation des 2 PNJ référence ([IA] Archiviste, [IA] Garde).
#
# Prérequis VM 245 : core3-clean + Lia en ligne sur tatooine, sidecar actif.
#
# Usage :
#   bash infra/scripts/smoke_core3_ia_phase_c1_reference_lan.sh
#   bash infra/scripts/smoke_core3_ia_phase_c1_reference_lan.sh --with-think

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
WITH_THINK=0
for arg in "$@"; do
  case "$arg" in
    --with-think) WITH_THINK=1 ;;
  esac
done

echo "=== Smoke C.1 — PNJ référence → ${VM_USER}@${VM_HOST} ==="

echo "--- 1) Catalogue + registre LBG (local) ---"
python3 <<PY
import json
import sys
from pathlib import Path

root = Path("${ROOT_DIR}")
reg = json.loads((root / "agents/src/lbg_agents/npc_registry.json").read_text())
cat_path = root / "content/core3/core3_npc_catalog.json"
pilots_path = root / "content/core3/core3_npc_pilots.json"
cat = json.loads(cat_path.read_text()) if cat_path.is_file() else None
pilots = json.loads(pilots_path.read_text())

required_npc = ("npc:scribe", "npc:guard")
by_id = {n["id"]: n for n in reg.get("npcs", []) if isinstance(n, dict)}
for nid in required_npc:
    n = by_id.get(nid)
    assert n, f"npc_registry manque {nid}"
    for key in ("name", "role", "tone", "summary", "goals", "constraints", "race_id"):
        assert n.get(key), f"{nid} manque {key}"
    c3 = n.get("core3_reference") or {}
    assert c3.get("pilot_id"), f"{nid} manque core3_reference.pilot_id"
    assert c3.get("c1_status") == "reference_active", f"{nid} c1_status"
    print(f"OK npc_registry {nid} -> pilot {c3['pilot_id']}")

if cat:
    assert cat.get("schema_version") == 2
    prof = cat.get("profiles") or {}
    entries = [e for e in cat.get("entries", []) if e.get("status") == "active"]
    assert len(entries) == 2, f"catalog: attendu 2 entries active, got {len(entries)}"
    for e in entries:
        assert e.get("profile_id") in prof, e
        print(f"OK catalog entry {e['pilot_id']} profile={e['profile_id']}")

for row in pilots.get("pilots", []):
    print(f"OK core3_npc_pilots {row.get('pilot_id')} lbg={row.get('lbg_npc_id')}")
assert len(pilots.get("pilots", [])) == 2
PY

echo "--- 2) Sidecar + snapshots (VM) ---"
ssh "${VM_USER}@${VM_HOST}" 'bash -s' <<'REMOTE'
set -euo pipefail
BASE="http://127.0.0.1:8791"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"
SNAP="${BIN}/ia_bridge/npc_snapshots.json"
PLAY="${BIN}/ia_bridge/pending.jsonl"

curl -sf "${BASE}/healthz" >/dev/null
python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen('${BASE}/healthz'))
assert d.get('phase') in ('C', 'C2') and d.get('npc_pilot_count')==2, d
print('OK healthz pilots=', d['npc_pilot_count'])
"

python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen('${BASE}/v1/npc-pilots'))
pilots=d.get('pilots') or []
assert len(pilots)==2, pilots
online=[p for p in pilots if p.get('online')]
assert len(online)==2, ('offline:', pilots)
for p in pilots:
    print('OK online', p.get('pilot_id'), 'name=', (p.get('snapshot') or {}).get('name'))
"

snaps={}
if [ -f "${SNAP}" ]; then
  python3 -c "
import json
snaps=json.load(open('${SNAP}'))
keys=list(snaps.keys())
assert len(keys)==2, ('snapshot keys:', keys)
for k,v in snaps.items():
    assert v.get('online'), k
    assert v.get('lbg_npc_id'), k
    print('OK snapshot', k, 'lbg=', v.get('lbg_npc_id'))
"
fi

# Pas de troupeau : au plus 2 lignes spawn récentes par pilote dans le log
if [ -f /tmp/core3-clean.log ]; then
  python3 -c "
import re
from collections import Counter
log=open('/tmp/core3-clean.log').read().splitlines()
spawns=[l for l in log if 'IaBridge: pilote spawn' in l]
# dernier boot : compter spawns par pilot_id dans les 30 dernières lignes spawn
recent=spawns[-20:]
ids=[]
for l in recent:
    m=re.search(r'spawn (npc:core3_\w+)', l)
    if m: ids.append(m.group(1))
c=Counter(ids)
bad={k:v for k,v in c.items() if v>3}
assert not bad, ('trop de respawn (troupeau?):', dict(c))
print('OK spawn log counts', dict(c) if c else 'no recent spawns')
"
fi

# Lia en ligne (optionnel mais recommandé C.1)
if [ -f "${BIN}/ia_bridge/player_snapshot.json" ]; then
  python3 -c "
import json
p=json.load(open('${BIN}/ia_bridge/player_snapshot.json'))
if not p.get('online'):
    print('WARN Lia hors ligne — tests think peuvent echouer')
else:
    print('OK Lia online zone=', p.get('zone'))
"
fi
REMOTE

if [[ "${WITH_THINK}" == "1" ]]; then
  echo "--- 3) npc-think (scribe + garde) ---"
  for NPC in npc:scribe npc:guard; do
    echo ">> ${NPC}"
    ssh "${VM_USER}@${VM_HOST}" "curl -sS --max-time 45 -X POST http://127.0.0.1:8791/v1/npc-think \
      -H 'Content-Type: application/json' \
      -d '{\"npc_id\":\"${NPC}\",\"prompt\":\"Une phrase d accueil courte.\",\"enqueue\":true}'" \
      | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d.get('ok'), d
assert d.get('action')=='npc_say', d
assert d.get('pilot_id','').startswith('npc:core3_'), d
print('OK', d['pilot_id'], 'line=', d.get('line','')[:80])
"
  done
  echo "Vérifiez en jeu : 2 spatial chats sous ~4 s."
fi

echo "=== Smoke C.1 terminé (OK) ==="
echo "Rapport : ${ROOT_DIR}/docs/core3_ia_phase_c1_reference.md"
