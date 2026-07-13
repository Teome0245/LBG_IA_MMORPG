#!/usr/bin/env bash
# Smoke — feed live prime-client (sidecar mirror → cache/zone_feed.json).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_PRIME="${LBG_CLIENT_PRIME_LBG_DIR:-/home/sdesh/projects/new_mmo/client-prime-lbg}"
CACHE_DIR="${LBG_PRIME_CLIENT_CACHE:-${CLIENT_PRIME}/../prime-client/cache}"
SIDECAR="${SIDECAR_URL:-http://192.168.0.246:8791}"

echo "=== Smoke prime-client live feed (${SIDECAR}) ==="
[[ -f "${CLIENT_PRIME}/sidecar_mirror.py" ]] || { echo "sidecar_mirror.py absent" >&2; exit 1; }

export SIDECAR_URL="${SIDECAR}"
export CACHE_DIR
export BOTS="${BOTS:-lia,nix,mira}"
python3 "${CLIENT_PRIME}/sidecar_mirror.py" --once > /tmp/lbg_prime_live_feed.json

python3 <<PY
import json, time
from pathlib import Path
out = json.loads(Path("/tmp/lbg_prime_live_feed.json").read_text())
assert out.get("health_ok"), out
assert int(out.get("online_count") or 0) >= 1, out
cache = Path("${CACHE_DIR}")
zf = json.loads((cache / "zone_feed.json").read_text())
ents = zf.get("entities") or []
assert len(ents) >= 1, zf
age = time.time() - (cache / "zone_feed.json").stat().st_mtime
assert age < 15, f"zone_feed.json trop vieux ({age:.1f}s)"
print(f"OK live feed: {len(ents)} entité(s), age={age:.1f}s")
PY

echo "Lancer Godot : godot4 --path ${CLIENT_PRIME}/../prime-client"
