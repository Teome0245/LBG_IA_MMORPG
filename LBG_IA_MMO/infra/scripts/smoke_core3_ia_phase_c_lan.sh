#!/usr/bin/env bash
# Smoke Phase C — PNJ pilotes + sidecar (VM 245).
#
# Usage :
#   bash infra/scripts/smoke_core3_ia_phase_c_lan.sh
#   bash infra/scripts/smoke_core3_ia_phase_c_lan.sh --with-think

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

echo "=== Smoke Core3 IA Phase C → ${VM_USER}@${VM_HOST} ==="

ssh "${VM_USER}@${VM_HOST}" 'bash -s' <<'REMOTE'
set -euo pipefail
BASE="http://127.0.0.1:8791"

echo "healthz phase C"
curl -sS "${BASE}/healthz" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d.get('ok') and d.get('phase')=='C', d
assert d.get('npc_pilot_count',0)>=1, d
print('OK phase=', d.get('phase'), 'pilots=', d.get('npc_pilot_count'))
"

echo "npc-pilots"
curl -sS "${BASE}/v1/npc-pilots" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d.get('ok'), d
pilots=d.get('pilots') or []
assert len(pilots)>=1, d
print('OK pilots listed:', len(pilots))
for p in pilots:
    print(' -', p.get('pilot_id'), 'online=', p.get('online'))
"

echo "npc-snapshot (scribe)"
code=$(curl -sS -o /tmp/npc_snap.json -w '%{http_code}' \
  "${BASE}/v1/npc-snapshot?npc_id=npc:scribe")
python3 -c "
import json,sys
code='${code}'
body=open('/tmp/npc_snap.json').read()
d=json.loads(body) if body.strip() else {}
print('HTTP', code, 'online=', d.get('snapshot',{}).get('online'))
if code != '200':
    print(body[:500])
    sys.exit(1)
assert d.get('ok'), d
"
REMOTE

if [[ "${WITH_THINK}" == "1" ]]; then
  echo "--- /v1/npc-think (LLM) ---"
  ssh "${VM_USER}@${VM_HOST}" 'curl -sS --max-time 45 -X POST http://127.0.0.1:8791/v1/npc-think \
    -H "Content-Type: application/json" \
    -d "{\"npc_id\":\"npc:scribe\",\"prompt\":\"Dis bonjour aux voyageurs en une phrase.\",\"enqueue\":true}"' \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(json.dumps(d, indent=2, ensure_ascii=False))
assert d.get('ok'), d
assert d.get('action') in ('npc_say','noop'), d
print('think OK action=', d.get('action'))
print('Vérifiez en jeu un spatial chat du PNJ pilote sous ~4 s.')
"
fi

echo "=== Smoke Phase C terminé ==="
