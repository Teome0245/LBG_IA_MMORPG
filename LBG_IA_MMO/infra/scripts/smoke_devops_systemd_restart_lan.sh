#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — DevOps systemd_restart (liste blanche), sans LLM.
#
# Appelle POST /v1/pilot/internal/route avec devops_action systemd_restart.
# Exécution réelle (systemctl restart) sauf si LBG_SMOKE_DEVOPS_RESTART_DRY=1 (dry-run côté context).
#
# Prérequis core (140) : dans /etc/lbg-ia-mmo.env (via push_secrets) :
#   LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST="lbg-backend.service,..."  (doit inclure LBG_SMOKE_DEVOPS_UNIT)
#
# Variables :
#   LBG_LAN_HOST_CORE             défaut 192.168.0.140
#   LBG_BACKEND_PORT              défaut 8000
#   LBG_PILOT_INTERNAL_TOKEN      optionnel (sinon lecture infra/secrets/lbg.env)
#   LBG_SMOKE_DEVOPS_UNIT         défaut lbg-agent-pm.service (évite de couper l’API backend pendant le smoke)
#   LBG_SMOKE_DEVOPS_RESTART_DRY  défaut 1 (dry-run) ; 0 = exécution réelle (exige devops_approval si gate actif)
#   LBG_SMOKE_DEVOPS_INCLUDE_APPROVAL défaut 0 ; si 1 et DRY=0, ajoute context.devops_approval depuis lbg.env
#   LBG_SMOKE_TIMEOUT_S           défaut 30

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
BACKEND_PORT="${LBG_BACKEND_PORT:-8000}"
UNIT="${LBG_SMOKE_DEVOPS_UNIT:-lbg-agent-pm.service}"
DRY="${LBG_SMOKE_DEVOPS_RESTART_DRY:-1}"
INCLUDE_APPROVAL="${LBG_SMOKE_DEVOPS_INCLUDE_APPROVAL:-0}"
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

approval=""
if [[ "${DRY}" == "0" && "${INCLUDE_APPROVAL}" == "1" ]]; then
  approval="$(read_env_var "LBG_DEVOPS_APPROVAL_TOKEN")"
fi

echo "=== Smoke LAN — DevOps systemd_restart ==="
echo "core=${CORE}:${BACKEND_PORT} unit=${UNIT} devops_dry_run=${dry_label} include_approval=${INCLUDE_APPROVAL} timeout_s=${TIMEOUT_S}"
echo ""

payload="$(
  UNIT="${UNIT}" DRY="${DRY}" APPROVAL="${approval}" python3 - <<'PY'
import json, os
unit = os.environ["UNIT"]
dry = os.environ.get("DRY", "1") == "1"
approval = (os.environ.get("APPROVAL") or "").strip()
ctx = {
    "devops_action": {"kind": "systemd_restart", "unit": unit},
    "devops_dry_run": dry,
}
if (not dry) and approval:
    ctx["devops_approval"] = approval
print(json.dumps({"actor_id": "svc:smoke_restart", "text": "restart unit", "context": ctx}))
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
assert r2.get("kind") == "systemd_restart", r2
dry = os.environ.get("DRY", "1") == "1"
if r2.get("ok") is not True:
    print("ERREUR:", str(r2.get("error") or r2)[:800], file=sys.stderr)
    raise SystemExit(1)
if dry:
    assert r2.get("dry_run") is True, r2
else:
    assert r2.get("exit_code") == 0, r2
print("OK: systemd_restart", "dry_run" if dry else "executed")
PY

echo ""
echo "Smoke DevOps systemd_restart (LAN) : OK"

