#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Smoke "réconciliation rejet" :
# - appelle directement l'HTTP interne mmmorpg_server avec un flag non supporté
# - attend HTTP 409 + accepted=false
#
# Usage:
#   bash infra/scripts/smoke_commit_reject_flag.sh
#
# Variables :
#   LBG_SMOKE_TIMEOUT_S défaut 30

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"

echo "== Commit reject smoke (mmmorpg internal HTTP) =="

if [[ -z "${TOKEN}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"
  if [[ -f "${SEC_FILE}" ]]; then
    TOKEN="$(
      python3 -c 'import re,sys,pathlib; p=sys.argv[1]; t="";
s=pathlib.Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
for line in s:
  m=re.match(r"^\s*LBG_MMMORPG_INTERNAL_HTTP_TOKEN\s*=\s*\"?(.*?)\"?\s*$", line)
  if m: t=m.group(1).strip(); break
print(t)' "${SEC_FILE}"
    )"
  fi
fi

MMO="${MMO}" PORT="${PORT}" NPC_ID="${NPC_ID}" TOKEN="${TOKEN}" TIMEOUT_S="${TIMEOUT_S}" python3 - <<'PY'
import json, os, subprocess, uuid

mmo = os.environ["MMO"]
port = os.environ["PORT"]
npc_id = os.environ["NPC_ID"]
token = os.environ.get("TOKEN", "").strip()
timeout_s = int(os.environ.get("TIMEOUT_S", "30") or "30")

url = f"http://{mmo}:{port}/internal/v1/npc/{npc_id}/dialogue-commit"
headers = ["-H", "content-type: application/json"]
if token:
    headers += ["-H", f"X-LBG-Service-Token: {token}"]

payload = {"trace_id": "smoke_bad_flag_" + uuid.uuid4().hex, "flags": {"__bad": "x"}}
cmd = ["curl", "-sS", "-i", "--connect-timeout", "3", "--max-time", str(timeout_s), url] + headers + ["-d", json.dumps(payload)]
raw = subprocess.check_output(cmd, text=True)
head, sep, body = raw.partition("\r\n\r\n")
if not sep:
    head, _, body = raw.partition("\n\n")
status_line = head.splitlines()[0] if head else ""
code = int(status_line.split()[1]) if len(status_line.split()) >= 2 else 0
print("http_status=", code)
print("body=", body.strip()[:200])
if code != 409:
    raise SystemExit("ERREUR: attendu HTTP 409")
j = json.loads(body)
if j.get("accepted") is not False:
    raise SystemExit("ERREUR: attendu accepted=false")
print("OK: commit rejeté (409)")
PY

