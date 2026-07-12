#!/usr/bin/env bash
# Watchdog SOE login Prime — sonde headless Bot_IA/Lia (soe_handshake --no-zone).
# Évite les faux négatifs UDP post-restart via grace period + seuil d'échecs consécutifs.
#
# Usage (VM 246 ou 140) :
#   bash infra/scripts/watch_core3_prime_soe_login_health.sh
#   bash .../watch_core3_prime_soe_login_health.sh --dry-run --json
#
# Variables (env ou /etc/lbg-ia-mmo.env) :
#   LBG_CORE3_PRIME_SOE_WATCHDOG_ENABLED=1
#   LBG_CORE3_PRIME_SOE_WATCHDOG_COOLDOWN_S=1800
#   LBG_CORE3_PRIME_SOE_WATCHDOG_FAIL_THRESHOLD=2
#   LBG_CORE3_PRIME_SOE_WATCHDOG_GRACE_AFTER_RESTART_S=120
#   LBG_SOE_HOST / LBG_SOE_LOGIN_PORT / LBG_SOE_USER / LBG_SOE_CHAR_NAME
#   LBG_CLIENT_PRIME_LBG_DIR

set -euo pipefail

LOG_TAG="core3_prime_soe_watchdog"
STATE_DIR="${LBG_CORE3_PRIME_SOE_WATCHDOG_STATE:-/var/lib/lbg/core3_prime_soe_watchdog}"
STATE_FILE="${STATE_DIR}/state.json"
PRIME_UNIT="${LBG_CORE3_PRIME_SERVICE:-lbg-core3-prime.service}"

DRY_RUN=0
JSON_OUT=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --json) JSON_OUT=1 ;;
  esac
done

_truthy() {
  case "${1:-}" in
    1 | true | yes | on | TRUE | YES | ON) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ -f /etc/lbg-ia-mmo.env ]]; then
  # shellcheck disable=SC1091
  set -a
  source /etc/lbg-ia-mmo.env
  set +a
fi

if ! _truthy "${LBG_CORE3_PRIME_SOE_WATCHDOG_ENABLED:-1}"; then
  [[ "${JSON_OUT}" == "1" ]] && echo '{"ok":true,"skipped":"disabled"}'
  exit 0
fi

COOLDOWN_S="${LBG_CORE3_PRIME_SOE_WATCHDOG_COOLDOWN_S:-1800}"
FAIL_THRESHOLD="${LBG_CORE3_PRIME_SOE_WATCHDOG_FAIL_THRESHOLD:-2}"
GRACE_S="${LBG_CORE3_PRIME_SOE_WATCHDOG_GRACE_AFTER_RESTART_S:-120}"
LOGIN_TIMEOUT_S="${LBG_SOE_M3_LOGIN_TIMEOUT_S:-95}"

CLIENT_PRIME="${LBG_CLIENT_PRIME_LBG_DIR:-/opt/new_mmo/client-prime-lbg}"
SOE_HOST="${LBG_SOE_HOST:-192.168.0.246}"
SOE_PORT="${LBG_SOE_LOGIN_PORT:-44553}"
SOE_USER="${LBG_SOE_USER:-Bot_IA}"
SOE_PASS="${LBG_SOE_PASSWORD:-lbgiabot}"
SOE_CHAR="${LBG_SOE_CHAR_NAME:-Lia}"

log() { echo "${LOG_TAG}: $*"; }

now_epoch() { date +%s; }

read_state() {
  mkdir -p "${STATE_DIR}" 2>/dev/null || true
  if [[ -f "${STATE_FILE}" ]]; then
    python3 -c "
import json
from pathlib import Path
try:
    print(json.dumps(json.loads(Path('${STATE_FILE}').read_text(encoding='utf-8'))))
except Exception:
    print('{}')
" 2>/dev/null || echo '{}'
  else
    echo '{}'
  fi
}

write_state_json() {
  local payload="$1"
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "${payload}" > "${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "${STATE_FILE}"
}

cooldown_active() {
  local state last_restart now
  state="$(read_state)"
  last_restart="$(echo "${state}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(float(d.get('last_restart_ts') or 0)))" 2>/dev/null || echo 0)"
  now="$(now_epoch)"
  [[ $((now - last_restart)) -lt "${COOLDOWN_S}" ]]
}

grace_after_restart() {
  local state last_restart now
  state="$(read_state)"
  last_restart="$(echo "${state}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(float(d.get('last_restart_ts') or 0)))" 2>/dev/null || echo 0)"
  [[ "${last_restart}" == "0" ]] && return 1
  now="$(now_epoch)"
  [[ $((now - last_restart)) -lt "${GRACE_S}" ]]
}

soe_login_probe_ok() {
  [[ -f "${CLIENT_PRIME}/soe_handshake.py" ]] || return 1
  local out rc=0
  set +e
  out="$(
    timeout "${LOGIN_TIMEOUT_S}" python3 "${CLIENT_PRIME}/soe_handshake.py" \
      --host "${SOE_HOST}" --port "${SOE_PORT}" \
      --user "${SOE_USER}" --password "${SOE_PASS}" \
      --char-name "${SOE_CHAR}" --no-zone 2>&1
  )"
  rc=$?
  set -e
  if echo "${out}" | grep -qE '\[Login\] OK connexion LoginServer terminee|\[LoginClientToken\]|\[EnumerateCharacterId\] [1-9]'; then
    return 0
  fi
  if echo "${out}" | grep -q '\[Login\] ECHEC'; then
    return 1
  fi
  [[ "${rc}" -eq 0 ]]
}

recover_prime() {
  local reason="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY-RUN: systemctl restart ${PRIME_UNIT} (${reason})"
    return 0
  fi
  log "restart ${PRIME_UNIT} (${reason})"
  sudo -n systemctl restart "${PRIME_UNIT}"
  python3 -c "
import json, time
from pathlib import Path
p = Path('${STATE_FILE}')
p.parent.mkdir(parents=True, exist_ok=True)
prev = {}
if p.is_file():
    try:
        prev = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        prev = {}
prev.update({
    'last_restart_ts': int(time.time()),
    'last_reason': '''${reason}''',
    'consecutive_failures': 0,
})
p.write_text(json.dumps(prev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
"
}

STATE="$(read_state)"
CONSEC="$(echo "${STATE}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(d.get('consecutive_failures') or 0))" 2>/dev/null || echo 0)"
PROBE_OK=0
soe_login_probe_ok && PROBE_OK=1 || true

if grace_after_restart; then
  log "grace post-restart (${GRACE_S}s) — skip probe/action"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"status\":\"grace\",\"probe_ok\":${PROBE_OK}}"
  exit 0
fi

if [[ "${PROBE_OK}" -eq 1 ]]; then
  write_state_json "$(python3 -c "
import json
from pathlib import Path
p = Path('${STATE_FILE}')
prev = {}
if p.is_file():
    try:
        prev = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        prev = {}
prev['consecutive_failures'] = 0
prev['last_probe_ok_ts'] = $(now_epoch)
print(json.dumps(prev, ensure_ascii=False))
")"
  [[ "${JSON_OUT}" == "1" ]] && echo '{"ok":true,"status":"healthy","probe_ok":true}'
  exit 0
fi

CONSEC=$((CONSEC + 1))
write_state_json "$(python3 -c "
import json
from pathlib import Path
p = Path('${STATE_FILE}')
prev = {}
if p.is_file():
    try:
        prev = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        prev = {}
prev['consecutive_failures'] = ${CONSEC}
prev['last_probe_fail_ts'] = $(now_epoch)
print(json.dumps(prev, ensure_ascii=False))
")"

log "échec SOE login ${CONSEC}/${FAIL_THRESHOLD} (${SOE_USER}/${SOE_CHAR} @ ${SOE_HOST}:${SOE_PORT})"

if [[ "${CONSEC}" -lt "${FAIL_THRESHOLD}" ]]; then
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"status\":\"degraded\",\"consecutive_failures\":${CONSEC}}"
  exit 0
fi

if cooldown_active; then
  log "cooldown actif — pas de restart"
  [[ "${JSON_OUT}" == "1" ]] && echo '{"ok":false,"status":"cooldown","action":"none"}'
  exit 0
fi

recover_prime "soe_login_failures_${CONSEC}"
[[ "${JSON_OUT}" == "1" ]] && echo '{"ok":false,"status":"recovered","action":"restart"}'
exit 0
