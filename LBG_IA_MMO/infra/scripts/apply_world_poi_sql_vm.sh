#!/usr/bin/env bash
# Applique la migration world_poi sur MariaDB Prime (VM 245).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
SQL="${ROOT}/infra/sql/world_poi_v1.sql"

echo "=== world_poi SQL → ${VM_USER}@${VM_HOST} ==="
scp -q "${SQL}" "${VM_USER}@${VM_HOST}:/tmp/world_poi_v1.sql"
ssh "${VM_USER}@${VM_HOST}" "mysql -u swgemu -p123456 swgemu < /tmp/world_poi_v1.sql && echo OK && mysql -u swgemu -p123456 swgemu -e 'SHOW TABLES LIKE \"world_poi%\";'"
echo "Migration world_poi appliquée."
