#!/usr/bin/env bash
# Smoke LAN — miroir sidecar 246 → cache Godot (client-prime-lbg).
#
# Usage :
#   bash infra/scripts/smoke_godot_sidecar_mirror_lan.sh
#   SIDECAR_URL=http://192.168.0.246:8791 bash infra/scripts/smoke_godot_sidecar_mirror_lan.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_PRIME="${LBG_CLIENT_PRIME_LBG_DIR:-/home/sdesh/projects/new_mmo/client-prime-lbg}"
SIDECAR="${SIDECAR_URL:-http://192.168.0.246:8791}"
SIDECAR="${SIDECAR%/}"

echo "=== Smoke Godot sidecar mirror (${SIDECAR}) ==="

if [[ ! -f "${CLIENT_PRIME}/sidecar_mirror.py" ]]; then
  echo "ERREUR: sidecar_mirror.py introuvable dans ${CLIENT_PRIME}" >&2
  echo "Définir LBG_CLIENT_PRIME_LBG_DIR si le chemin diffère." >&2
  exit 1
fi

echo "1) healthz sidecar"
curl -sf "${SIDECAR}/healthz" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok') is not False, d"

echo "2) mirror --once"
CACHE_DIR="$(mktemp -d)"
export SIDECAR_URL="${SIDECAR}"
export CACHE_DIR
export BOTS="${BOTS:-lia,nix,mira}"
python3 "${CLIENT_PRIME}/sidecar_mirror.py" --once > /tmp/lbg_godot_mirror_out.json
python3 <<'PY'
import json
with open("/tmp/lbg_godot_mirror_out.json") as f:
    out = json.load(f)
assert out.get("health_ok"), out
assert int(out.get("online_count") or 0) >= 1, out
print("OK mirror:", out.get("online_count"), "bot(s) online")
PY

echo "3) zone_feed.json valide"
python3 <<PY
import json
from pathlib import Path
cache = Path("${CACHE_DIR}")
zf = json.loads((cache / "zone_feed.json").read_text())
ents = zf.get("entities") or []
assert len(ents) >= 1, zf
assert ents[0].get("kind") == "player", ents[0]
print("OK zone_feed:", len(ents), "entité(s)")
PY

echo ""
echo "Tout vert — lancer Godot : godot4 --path ${CLIENT_PRIME}/../prime-client"
echo "Doc : docs/jalon_client_godot_sidecar_246.md"
