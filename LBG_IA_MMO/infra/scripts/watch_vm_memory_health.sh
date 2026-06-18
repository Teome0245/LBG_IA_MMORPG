#!/usr/bin/env bash
# Sonde mémoire locale (VM Prime 246) — log + état JSON, restart Prime optionnel.
# Usage : bash infra/scripts/watch_vm_memory_health.sh [--json]
set -euo pipefail

STATE_DIR="${LBG_VM_MEMORY_WATCHDOG_STATE:-${HOME}/.local/state/lbg/vm_memory_watchdog}"
STATE_FILE="${STATE_DIR}/state.json"
JSON_OUT=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON_OUT=1 ;;
  esac
done

_truthy() {
  case "${1:-}" in
    1 | true | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

if ! _truthy "${LBG_VM_MEMORY_WATCHDOG_ENABLED:-1}"; then
  [[ "${JSON_OUT}" == "1" ]] && echo '{"ok":true,"skipped":"disabled"}'
  exit 0
fi

WARN_AVAIL_MB="${LBG_VM_MEMORY_WARN_AVAIL_MB:-800}"
CRIT_AVAIL_MB="${LBG_VM_MEMORY_CRIT_AVAIL_MB:-300}"
COOLDOWN_S="${LBG_VM_MEMORY_WATCHDOG_COOLDOWN_S:-3600}"
RESTART="${LBG_VM_MEMORY_WATCHDOG_RESTART:-0}"

read -r mem_total mem_avail swap_total swap_used < <(
  LC_ALL=C free -m | awk '/^Mem:/{mt=$2; ma=$7} /^Swap:/{st=$2; su=$3} END{print mt+0, ma+0, st+0, su+0}'
)
core3_rss_kb="$(ps -C core3-clean -o rss= 2>/dev/null | awk '{s+=$1} END {print s+0}')"
core3_rss_mb=$((core3_rss_kb / 1024))

status="ok"
reasons=()
if [[ "${mem_avail}" -lt "${CRIT_AVAIL_MB}" ]]; then
  status="critical"
  reasons+=("mem_avail_mb:${mem_avail}<${CRIT_AVAIL_MB}")
elif [[ "${mem_avail}" -lt "${WARN_AVAIL_MB}" ]]; then
  status="warn"
  reasons+=("mem_avail_mb:${mem_avail}<${WARN_AVAIL_MB}")
fi
if [[ "${swap_total}" -gt 0 ]] && [[ $((swap_used * 100 / swap_total)) -ge 80 ]]; then
  status="critical"
  reasons+=("swap_high")
fi

payload="$(python3 -c "
import json, time
print(json.dumps({
  'ts': time.time(),
  'status': '${status}',
  'mem_total_mb': ${mem_total},
  'mem_avail_mb': ${mem_avail},
  'swap_total_mb': ${swap_total},
  'swap_used_mb': ${swap_used},
  'core3_rss_mb': ${core3_rss_mb},
  'reasons': '''${reasons[*]:-}'''.split() if '''${reasons[*]:-}''' else [],
}, ensure_ascii=False))
")"

mkdir -p "${STATE_DIR}"
printf '%s\n' "${payload}" > "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "${STATE_FILE}"

if [[ "${JSON_OUT}" == "1" ]]; then
  echo "${payload}"
fi

if [[ "${status}" == "critical" ]] && _truthy "${RESTART}" ]]; then
  last=0
  if [[ -f "${STATE_FILE}" ]]; then
    last="$(python3 -c "import json; print(json.loads(open('${STATE_FILE}').read()).get('last_restart_ts') or 0)" 2>/dev/null || echo 0)"
  fi
  now="$(date +%s)"
  if [[ $((now - last)) -ge "${COOLDOWN_S}" ]]; then
    echo "vm_memory_watchdog: restart Prime (mem_avail=${mem_avail}MiB core3=${core3_rss_mb}MiB)"
    sudo -n systemctl restart lbg-core3-prime.service || true
    python3 -c "
import json, time
from pathlib import Path
p = Path('${STATE_FILE}')
d = json.loads(p.read_text())
d['last_restart_ts'] = time.time()
p.write_text(json.dumps(d, indent=2) + '\n')
"
  fi
fi

[[ "${status}" == "critical" ]] && exit 2
[[ "${status}" == "warn" ]] && exit 1
exit 0
