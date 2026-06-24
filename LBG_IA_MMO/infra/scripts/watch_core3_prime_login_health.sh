#!/usr/bin/env bash
# Watchdog Serveur Prime — détecte le blocage login connu (uptime longue + StreamIndexOutOfBounds
# + échec auth headless) et redémarre lbg-core3-prime.service (post_prime_ia_bots via ExecStartPost).
#
# Usage (VM 245) :
#   bash /opt/LBG_IA_MMO/infra/scripts/watch_core3_prime_login_health.sh
#   bash .../watch_core3_prime_login_health.sh --dry-run
#   bash .../watch_core3_prime_login_health.sh --json
#
# Variables (env ou /etc/lbg-ia-mmo.env) :
#   LBG_CORE3_PRIME_WATCHDOG_ENABLED=1
#   LBG_CORE3_PRIME_WATCHDOG_COOLDOWN_S=2700
#   LBG_CORE3_PRIME_WATCHDOG_STREAM_ERRORS=4
#   LBG_CORE3_PRIME_WATCHDOG_LOGIN_TIMEOUT_S=50
#   LBG_CORE3_PRIME_WATCHDOG_MIN_UPTIME_S=600
#   LBG_CORE3_PRIME_WATCHDOG_GRACE_AFTER_RESTART_S=900

set -euo pipefail

LOG_TAG="core3_prime_watchdog"
BIN_DIR="${CORE3_BIN_DIR:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
ENV_FILE="${CORE3_CLIENT_ENV_FILE:-${BIN_DIR}/.env-core3client}"
STATE_DIR="${LBG_CORE3_PRIME_WATCHDOG_STATE:-/var/lib/lbg/core3_prime_watchdog}"
STATE_FILE="${STATE_DIR}/state.json"
CORE3_LOG="${BIN_DIR}/log/core3.log"
CLIENT_LOG="${BIN_DIR}/log/core3client.log"

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

if ! _truthy "${LBG_CORE3_PRIME_WATCHDOG_ENABLED:-1}"; then
  [[ "${JSON_OUT}" == "1" ]] && echo '{"ok":true,"skipped":"disabled"}'
  exit 0
fi

COOLDOWN_S="${LBG_CORE3_PRIME_WATCHDOG_COOLDOWN_S:-2700}"
STREAM_THRESHOLD="${LBG_CORE3_PRIME_WATCHDOG_STREAM_ERRORS:-4}"
LOGIN_TIMEOUT_S="${LBG_CORE3_PRIME_WATCHDOG_LOGIN_TIMEOUT_S:-50}"
MIN_UPTIME_S="${LBG_CORE3_PRIME_WATCHDOG_MIN_UPTIME_S:-600}"
GRACE_AFTER_RESTART_S="${LBG_CORE3_PRIME_WATCHDOG_GRACE_AFTER_RESTART_S:-900}"

log() { echo "${LOG_TAG}: $*"; }

now_epoch() { date +%s; }

read_state() {
  mkdir -p "${STATE_DIR}" 2>/dev/null || true
  if [[ -f "${STATE_FILE}" ]]; then
    python3 -c "
import json, sys
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

write_state() {
  local payload="$1"
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "${payload}" > "${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "${STATE_FILE}"
}

prime_pid() {
  pgrep -x core3-clean 2>/dev/null | head -1 || true
}

prime_uptime_s() {
  local pid
  pid="$(prime_pid)"
  [[ -n "${pid}" ]] || { echo 0; return; }
  ps -o etimes= -p "${pid}" 2>/dev/null | tr -d ' ' || echo 0
}

zone_up() {
  [[ -f "${CORE3_LOG}" ]] || return 1
  grep -q "started on port 44563" "${CORE3_LOG}" 2>/dev/null
}

count_stream_errors() {
  [[ -f "${CORE3_LOG}" ]] || { echo 0; return; }
  tail -n 2500 "${CORE3_LOG}" 2>/dev/null | grep -c 'StreamIndexOutOfBoundsException' || echo 0
}

recent_headless_login_timeout() {
  [[ -f "${CLIENT_LOG}" ]] || return 1
  local tail
  tail="$(tail -n 400 "${CLIENT_LOG}" 2>/dev/null || true)"
  echo "${tail}" | grep -q 'Login process timed out'
}

login_probe_ok() {
  local client="${BIN_DIR}/core3client"
  [[ -x "${client}" && -f "${ENV_FILE}" ]] || return 1
  local out rc=0
  set +e
  out="$(
    cd "${BIN_DIR}" && timeout "${LOGIN_TIMEOUT_S}" ./core3client --env "${ENV_FILE}" --login-only 2>&1
  )"
  rc=$?
  set -e
  if echo "${out}" | grep -qE 'Authentication successful|Login process completed successfully'; then
    return 0
  fi
  if echo "${out}" | grep -q 'Login process timed out'; then
    return 1
  fi
  [[ "${rc}" -eq 0 ]] && return 0
  return 1
}

lia_sidecar_online() {
  local raw
  raw="$(curl -sS -m 12 'http://127.0.0.1:8791/v1/player-snapshot?player=Lia' 2>/dev/null || true)"
  echo "${raw}" | grep -q '"online": true'
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
  [[ $((now - last_restart)) -lt "${GRACE_AFTER_RESTART_S}" ]]
}

recover_prime() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY-RUN: systemctl restart lbg-core3-prime.service"
    return 0
  fi
  log "redémarrage lbg-core3-prime.service (blocage login détecté)"
  sudo -n systemctl restart lbg-core3-prime.service
  python3 -c "
import json, time
from pathlib import Path
p = Path('${STATE_FILE}')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({
    'last_restart_ts': int(time.time()),
    'last_reason': '''${RECOVER_REASON:-unknown}''',
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
"
}

# --- collecte signaux ---
PID="$(prime_pid)"
UPTIME="$(prime_uptime_s)"
STREAM_ERRS="$(count_stream_errors)"
ZONE_OK=0
zone_up && ZONE_OK=1 || true

REASONS=()
HEALTHY=1

if [[ -z "${PID}" ]]; then
  HEALTHY=0
  REASONS+=("prime_down")
elif [[ "${ZONE_OK}" -eq 0 ]]; then
  if [[ "${UPTIME}" -gt "${MIN_UPTIME_S}" ]]; then
    HEALTHY=0
    REASONS+=("zone_not_up")
  else
    log "Prime en boot (uptime=${UPTIME}s) — skip"
    [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"status\":\"booting\",\"uptime_s\":${UPTIME}}"
    exit 0
  fi
fi

if grace_after_restart; then
  log "grace après restart — skip probes"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"status\":\"grace_after_restart\",\"uptime_s\":${UPTIME}}"
  exit 0
fi

if [[ "${UPTIME}" -lt "${MIN_UPTIME_S}" ]]; then
  log "uptime ${UPTIME}s < ${MIN_UPTIME_S}s — skip"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"status\":\"warming_up\",\"uptime_s\":${UPTIME}}"
  exit 0
fi

LOGIN_OK=0
if login_probe_ok; then
  LOGIN_OK=1
else
  REASONS+=("login_probe_failed")
  HEALTHY=0
fi

if [[ "${STREAM_ERRS}" -ge "${STREAM_THRESHOLD}" ]]; then
  REASONS+=("stream_index_errors:${STREAM_ERRS}")
  HEALTHY=0
fi

if recent_headless_login_timeout; then
  REASONS+=("headless_login_timeout_log")
  HEALTHY=0
fi

# Lia offline alors que le sidecar répond : souvent session fantôme post-blocage
if [[ "${LOGIN_OK}" -eq 0 ]] && ! lia_sidecar_online; then
  REASONS+=("lia_offline")
fi

REASONS_JOINED="$(IFS=,; echo "${REASONS[*]:-}")"

if [[ "${HEALTHY}" -eq 1 ]]; then
  log "OK uptime=${UPTIME}s login_probe=ok stream_errors=${STREAM_ERRS}"
  write_state "$(python3 -c "import json,time; print(json.dumps({'last_ok_ts': int(time.time()), 'uptime_s': ${UPTIME}, 'stream_errors': ${STREAM_ERRS}}))")"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"healthy\":true,\"uptime_s\":${UPTIME},\"stream_errors\":${STREAM_ERRS}}"
  exit 0
fi

log "UNHEALTHY uptime=${UPTIME}s reasons=${REASONS_JOINED} stream_errors=${STREAM_ERRS} login_ok=${LOGIN_OK}"

BYPASS_COOLDOWN=0
if [[ " ${REASONS[*]} " == *" prime_down "* ]]; then
  BYPASS_COOLDOWN=1
fi

if cooldown_active && [[ "${BYPASS_COOLDOWN}" -eq 0 ]]; then
  log "cooldown actif (${COOLDOWN_S}s) — pas de restart"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":false,\"healthy\":false,\"cooldown\":true,\"reasons\":\"${REASONS_JOINED}\",\"uptime_s\":${UPTIME}}"
  exit 2
fi

RECOVER_REASON="${REASONS_JOINED}"
recover_prime
sleep 5
if systemctl is-active --quiet lbg-core3-prime.service 2>/dev/null; then
  log "restart OK — post_prime_ia_bots via ExecStartPost"
  [[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":true,\"recovered\":true,\"reasons\":\"${REASONS_JOINED}\"}"
  exit 0
fi

log "ERROR: restart Prime échoué"
[[ "${JSON_OUT}" == "1" ]] && echo "{\"ok\":false,\"recovered\":false,\"reasons\":\"${REASONS_JOINED}\"}"
exit 3
