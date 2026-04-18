#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — jalon MMO v1 gameplay #2 : WebSocket `move` + `world_commit` (sans LLM)
# → variation mesurable sur snapshot HTTP interne (`lyra.meta.reputation`).
#
# Usage (depuis LBG_IA_MMO/) :
#   bash infra/scripts/smoke_ws_move_commit_snapshot_lan.sh
#
# Variables :
#   LBG_LAN_HOST_MMO              défaut 192.168.0.245
#   LBG_MMMORPG_WS_PORT           défaut 7733
#   LBG_MMMORPG_INTERNAL_PORT     défaut 8773
#   LBG_SMOKE_NPC_ID              défaut npc:merchant
#   LBG_SMOKE_TIMEOUT_S           défaut 45
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (sinon lecture infra/secrets/lbg.env)
#   LBG_SMOKE_REP_DELTA_WS        défaut 7 (reputation_delta dans world_commit.flags)
#

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
WS_PORT="${LBG_MMMORPG_WS_PORT:-7733}"
HTTP_PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-45}"
REP_DELTA="${LBG_SMOKE_REP_DELTA_WS:-7}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"

read_env_var() {
  local key="$1"
  python3 - <<'PY' "$SEC_FILE" "$key"
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not p.exists():
    print("")
    raise SystemExit(0)
pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*\"?(.*?)\"?\s*$")
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    m = pat.match(line)
    if m:
        print(m.group(1).strip())
        raise SystemExit(0)
print("")
PY
}

if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_MMMORPG_INTERNAL_HTTP_TOKEN")"
fi

echo "=== Smoke LAN — WS move + world_commit → snapshot (jalon #2) ==="
echo "mmo=${MMO} ws=${WS_PORT} internal=${HTTP_PORT} npc=${NPC_ID} rep_delta=${REP_DELTA} timeout_s=${TIMEOUT_S}"
echo ""

PY="python3"
if [[ -x "${ROOT_DIR}/.venv-ci/bin/python" ]]; then
  PY="${ROOT_DIR}/.venv-ci/bin/python"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PY="${ROOT_DIR}/.venv/bin/python"
fi
export PYTHONPATH="${ROOT_DIR}/mmmorpg_server/src${PYTHONPATH:+:${PYTHONPATH}}"
"${PY}" "${ROOT_DIR}/mmmorpg_server/tools/ws_world_commit_smoke.py" \
  --ws "ws://${MMO}:${WS_PORT}" \
  --internal "http://${MMO}:${HTTP_PORT}" \
  --npc-id "${NPC_ID}" \
  --token "${TOKEN}" \
  --reputation-delta "${REP_DELTA}" \
  --timeout "${TIMEOUT_S}"

echo ""
echo "Smoke WS move + world_commit (LAN) : OK"
