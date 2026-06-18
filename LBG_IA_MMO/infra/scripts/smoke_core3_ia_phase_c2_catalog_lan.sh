#!/usr/bin/env bash
# Smoke C.2 — sidecar lit core3_npc_catalog.json (profils LLM).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

echo "=== Smoke C.2 — catalogue → ${VM_USER}@${VM_HOST} ==="

bash "${ROOT_DIR}/infra/scripts/smoke_core3_ia_phase_c1_reference_lan.sh" "$@"

ssh "${VM_USER}@${VM_HOST}" 'python3 -c "
import json, urllib.request
d=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/healthz\"))
assert d.get(\"phase\")==\"C2\", d
assert d.get(\"registry_source\")==\"catalog\", d
print(\"OK phase C2 catalog source=\", d.get(\"registry_source\"))
pl=json.load(urllib.request.urlopen(\"http://127.0.0.1:8791/v1/npc-pilots\"))
for p in pl.get(\"pilots\") or []:
    hint=p.get(\"llm_system_hint\")
    assert hint, (p.get(\"pilot_id\"), p)
    print(\"OK profile hint\", p.get(\"pilot_id\"), hint[:40])
"'

echo "=== Smoke C.2 terminé ==="
