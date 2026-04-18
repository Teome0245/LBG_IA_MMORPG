#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — DevOps selfcheck (bundle HTTP + systemd, listes blanches).
#
# POST /v1/pilot/internal/route avec devops_action {"kind":"selfcheck"} (dry-run par défaut).
#
# Prérequis : LBG_DEVOPS_HTTP_ALLOWLIST sur le core si les healthz LAN ne sont pas dans les défauts 127.0.0.1 ;
# LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST pour les étapes systemd (sinon uniquement HTTP).
#
# Variables : LBG_LAN_HOST_CORE, LBG_BACKEND_PORT, LBG_PILOT_INTERNAL_TOKEN, LBG_SMOKE_TIMEOUT_S,
#   LBG_SMOKE_DEVOPS_SELFCHECK_DRY (défaut 1)

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
DRY="${LBG_SMOKE_DEVOPS_SELFCHECK_DRY:-1}"
TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"

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

if [[ -z "${PILOT_TOKEN}" ]]; then
  PILOT_TOKEN="$(read_env_var "LBG_PILOT_INTERNAL_TOKEN")"
fi

hdr_pilot=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_pilot=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

dry_label="false"
if [[ "${DRY}" == "1" ]]; then
  dry_label="true"
fi

echo "=== Smoke LAN — DevOps selfcheck ==="
echo "core=${CORE}:${BACKEND_PORT} devops_dry_run=${dry_label} timeout_s=${TIMEOUT_S}"
echo ""

payload="$(
  DRY="${DRY}" python3 - <<'PY'
import json, os

dry = os.environ.get("DRY", "1") == "1"
print(
    json.dumps(
        {
            "actor_id": "svc:smoke_selfcheck",
            "text": "diagnostic complet",
            "context": {
                "devops_action": {"kind": "selfcheck"},
                "devops_dry_run": dry,
            },
        }
    )
)
PY
)"

resp="$(
  curl -sS --connect-timeout 3 --max-time "${TIMEOUT_S}" \
    "${hdr_pilot[@]}" \
    -H "content-type: application/json" \
    -d "${payload}" \
    "http://${CORE}:${BACKEND_PORT}/v1/pilot/internal/route"
)"

OUT="${resp}" DRY="${DRY}" python3 - <<'PY'
import json, os, sys

j = json.loads(os.environ["OUT"])
assert j.get("ok") is True, f"ok=true attendu, reçu: {j!r}"[:2000]
res = j.get("result") or {}
assert res.get("intent") == "devops_probe", res
out = res.get("output") or {}
r2 = out.get("result")
assert isinstance(r2, dict), f"output.result dict attendu: {out!r}"[:2000]
assert r2.get("kind") == "selfcheck", r2
if r2.get("ok") is not True:
    print("ERREUR:", str(r2)[:800], file=sys.stderr)
    raise SystemExit(1)
steps = r2.get("steps")
assert isinstance(steps, list) and len(steps) >= 1, r2
dry = os.environ.get("DRY", "1") == "1"
if dry:
    assert r2.get("dry_run") is True, r2
print("OK: selfcheck", len(steps), "étapes", "dry_run" if dry else "executed")
PY

echo ""
echo "Smoke DevOps selfcheck (LAN) : OK"
