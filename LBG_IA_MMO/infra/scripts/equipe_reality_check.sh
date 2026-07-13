#!/usr/bin/env bash
# Reality-check équipe virtuelle — orchestrateur 140, bridge OpenClaw, Ollama 110, SOE 246, M9, autoconsult.
#
# Usage :
#   bash infra/scripts/equipe_reality_check.sh
#   bash infra/scripts/equipe_reality_check.sh --json
#
# Variables :
#   LBG_CORE_VM_HOST       défaut 192.168.0.140
#   LBG_LAN_HOST_FRONT     défaut 192.168.0.110 (Ollama)
#   LBG_SOE_HOST           défaut 192.168.0.246
#   LBG_ORCHESTRATOR_URL   défaut http://192.168.0.140:8010

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JSON_OUT=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON_OUT=1 ;;
  esac
done

CORE_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
FRONT_HOST="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
SOE_HOST="${LBG_SOE_HOST:-192.168.0.246}"
VM_USER="${LBG_CORE_VM_USER:-lbg}"
ORCH="${LBG_ORCHESTRATOR_URL:-http://${CORE_HOST}:8010}"

declare -A CHECKS=()
FAIL=0

mark() {
  local key="$1" ok="$2" detail="${3:-}"
  CHECKS["${key}_ok"]="${ok}"
  CHECKS["${key}_detail"]="${detail}"
  if [[ "${ok}" != "1" ]]; then
    FAIL=1
  fi
}

log_step() {
  [[ "${JSON_OUT}" == "1" ]] || echo "=== $* ==="
}

# --- Orchestrateur 140 ---
log_step "Orchestrateur ${ORCH}"
if curl -sf --max-time 8 "${ORCH}/healthz" >/dev/null 2>&1; then
  mark orchestrator 1 "healthz OK"
else
  mark orchestrator 0 "healthz KO"
fi

# --- Bridge OpenClaw (localhost sur 140) ---
log_step "Bridge OpenClaw 140:18790"
BRIDGE_JSON="$(ssh -o ConnectTimeout=6 "${VM_USER}@${CORE_HOST}" "curl -sf --max-time 5 http://127.0.0.1:18790/healthz 2>/dev/null || echo FAIL" 2>/dev/null || echo FAIL)"
if [[ "${BRIDGE_JSON}" != "FAIL" && -n "${BRIDGE_JSON}" ]]; then
  mark openclaw_bridge 1 "healthz OK"
else
  mark openclaw_bridge 0 "healthz KO ou SSH"
fi

# --- Audit Ollama 110 ---
log_step "Audit Ollama ${FRONT_HOST}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://${FRONT_HOST}:11434}"
AUDIT_JSON="$(cd "${ROOT_DIR}/orchestrator" && PYTHONPATH=.:../agents/src ../orchestrator/.venv/bin/python -c "
from team.ollama_audit import audit_ollama_lan
import json
print(json.dumps(audit_ollama_lan(), ensure_ascii=False))
" 2>/dev/null || echo '{"ok":false,"gaps":["audit_failed"]}')"
AUDIT_OK="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(1 if d.get('ok') and not d.get('gaps') else 0)" "${AUDIT_JSON}" 2>/dev/null || echo 0)"
GAPS="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(','.join(d.get('gaps') or []))" "${AUDIT_JSON}" 2>/dev/null || echo audit_failed)"
mark ollama_audit "${AUDIT_OK}" "${GAPS:-ok}"

# --- SOE M3 login (depuis core 140 — UDP fiable) ---
log_step "SOE M3 login ${SOE_HOST}:44553 (via core ${CORE_HOST})"
set +e
SOE_OUT="$(ssh -o ConnectTimeout=8 "${VM_USER}@${CORE_HOST}" "set -a; . /etc/lbg-ia-mmo.env; set +a; bash /opt/LBG_IA_MMO/infra/scripts/smoke_soe_m3_login_lan.sh" 2>&1)"
SOE_RC=$?
set -e
if [[ "${SOE_RC}" -eq 0 ]]; then
  mark soe_m3_login 1 "login OK (140)"
else
  mark soe_m3_login 0 "$(echo "${SOE_OUT}" | tail -3 | tr '\n' ' ')"
fi

# --- SOE M3 zone (Lia → ZoneServer, via 140) ---
log_step "SOE M3 zone ${SOE_HOST} (via core ${CORE_HOST})"
set +e
ZONE_OUT="$(ssh -o ConnectTimeout=8 "${VM_USER}@${CORE_HOST}" "set -a; . /etc/lbg-ia-mmo.env; set +a; export LBG_SOE_M3_ZONE_TIMEOUT_S=\${LBG_SOE_M3_ZONE_TIMEOUT_S:-120}; cd /opt/LBG_IA_MMO/orchestrator && PYTHONPATH=.:../agents/src timeout 150 /opt/LBG_IA_MMO/.venv/bin/python -c \"from team.godot_soe_probe import probe_soe_m3_zone; import json; print(json.dumps(probe_soe_m3_zone()))\"" 2>&1)"
ZONE_RC=$?
set -e
ZONE_OK="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(1 if d.get('ok') else 0)" "${ZONE_OUT}" 2>/dev/null || echo 0)"
if [[ "${ZONE_OK}" == "1" ]]; then
  mark soe_m3_zone 1 "zone OK (140)"
else
  mark soe_m3_zone 0 "$(echo "${ZONE_OUT}" | tail -2 | tr '\n' ' ')"
fi

# --- M9 minimap (fichiers locaux ou chemins env) ---
log_step "M9 minimap Prime Client"
set +e
M9_OUT="$(bash "${ROOT_DIR}/infra/scripts/smoke_prime_client_minimap.sh" 2>&1)"
M9_RC=$?
set -e
if [[ "${M9_RC}" -eq 0 ]]; then
  mark m9_minimap 1 "smoke OK"
else
  mark m9_minimap 0 "$(echo "${M9_OUT}" | tail -2 | tr '\n' ' ')"
fi

# --- SOE M5 play (prime_controller, via 140) ---
log_step "SOE M5 play ${SOE_HOST} (via core ${CORE_HOST})"
set +e
M5_OUT="$(ssh -o ConnectTimeout=8 "${VM_USER}@${CORE_HOST}" "set -a; . /etc/lbg-ia-mmo.env; set +a; bash /opt/LBG_IA_MMO/infra/scripts/smoke_soe_m5_play_lan.sh" 2>&1)"
M5_RC=$?
set -e
if [[ "${M5_RC}" -eq 0 ]]; then
  mark soe_m5_play 1 "play OK (140)"
else
  mark soe_m5_play 0 "$(echo "${M5_OUT}" | tail -3 | tr '\n' ' ')"
fi

# --- Godot sidecar mirror 246 ---
log_step "Godot sidecar mirror ${SOE_HOST}:8791"
set +e
SIDECAR_OUT="$(bash "${ROOT_DIR}/infra/scripts/smoke_godot_sidecar_mirror_lan.sh" 2>&1)"
SIDECAR_RC=$?
set -e
if [[ "${SIDECAR_RC}" -eq 0 ]]; then
  mark godot_sidecar 1 "mirror OK"
else
  mark godot_sidecar 0 "$(echo "${SIDECAR_OUT}" | tail -2 | tr '\n' ' ')"
fi

# --- Dernier autoconsult (state 140 + tâche PM récente) ---
log_step "Autoconsult state 140"
STATE_RAW="$(ssh -o ConnectTimeout=6 "${VM_USER}@${CORE_HOST}" \
  "cat /var/lib/lbg/team_autoconsult/state.json 2>/dev/null || echo '{}'" 2>/dev/null || echo '{}')"
AUTO_OK="$(python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    d = {}
ok = d.get('last_task_ok')
if ok is True:
    print(1)
elif ok is False:
    print(0)
else:
    print(-1)
" "${STATE_RAW}" 2>/dev/null || echo -1)"
TASK_ID="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('last_task_id','') or 'none')" "${STATE_RAW}" 2>/dev/null || echo none)"
# Fallback : dernière tâche PM autoconsult via API
if [[ "${AUTO_OK}" != "1" ]]; then
  RECENT="$(curl -sf --max-time 8 "${ORCH}/v1/team/tasks?limit=20" 2>/dev/null || echo '[]')"
  API_OK="$(python3 -c "
import json, sys
try:
    tasks = json.loads(sys.argv[1])
except Exception:
    tasks = []
for t in tasks if isinstance(tasks, list) else []:
    ctx = t.get('context') or {}
    if not ctx.get('autoconsult_round'):
        continue
    res = t.get('result') or {}
    if res.get('kind') == 'autoconsult_workflow' and res.get('ok') is True:
        print(1)
        break
else:
    print(0)
" "${RECENT}" 2>/dev/null || echo 0)"
  if [[ "${API_OK}" == "1" ]]; then
    AUTO_OK=1
    TASK_ID="api-recent"
  fi
fi
if [[ "${AUTO_OK}" == "1" ]]; then
  mark autoconsult 1 "last_task_ok=true id=${TASK_ID}"
elif [[ "${AUTO_OK}" == "0" ]]; then
  mark autoconsult 0 "last_task_ok=false id=${TASK_ID}"
  FAIL=1
else
  mark autoconsult 1 "no prior round (skipped)"
fi

# --- Prime UDP 44553 (port ouvert) ---
log_step "Prime UDP ${SOE_HOST}:44553"
if nc -zvu -w 2 "${SOE_HOST}" 44553 2>&1 | grep -q succeeded; then
  mark prime_udp 1 "UDP open"
else
  mark prime_udp 0 "UDP closed"
fi

if [[ "${JSON_OUT}" == "1" ]]; then
  export RC_FAIL="${FAIL}"
  export RC_ORCH_OK="${CHECKS[orchestrator_ok]:-0}" RC_ORCH_DETAIL="${CHECKS[orchestrator_detail]:-}"
  export RC_BRIDGE_OK="${CHECKS[openclaw_bridge_ok]:-0}" RC_BRIDGE_DETAIL="${CHECKS[openclaw_bridge_detail]:-}"
  export RC_OLLAMA_OK="${CHECKS[ollama_audit_ok]:-0}" RC_OLLAMA_DETAIL="${CHECKS[ollama_audit_detail]:-}"
  export RC_SOE_OK="${CHECKS[soe_m3_login_ok]:-0}" RC_SOE_DETAIL="${CHECKS[soe_m3_login_detail]:-}"
  export RC_ZONE_OK="${CHECKS[soe_m3_zone_ok]:-0}" RC_ZONE_DETAIL="${CHECKS[soe_m3_zone_detail]:-}"
  export RC_M5_OK="${CHECKS[soe_m5_play_ok]:-0}" RC_M5_DETAIL="${CHECKS[soe_m5_play_detail]:-}"
  export RC_SIDECAR_OK="${CHECKS[godot_sidecar_ok]:-0}" RC_SIDECAR_DETAIL="${CHECKS[godot_sidecar_detail]:-}"
  export RC_M9_OK="${CHECKS[m9_minimap_ok]:-0}" RC_M9_DETAIL="${CHECKS[m9_minimap_detail]:-}"
  export RC_AUTO_OK="${CHECKS[autoconsult_ok]:-0}" RC_AUTO_DETAIL="${CHECKS[autoconsult_detail]:-}"
  export RC_UDP_OK="${CHECKS[prime_udp_ok]:-0}" RC_UDP_DETAIL="${CHECKS[prime_udp_detail]:-}"
  python3 -c "
import json, os
payload = {
    'ok': os.environ.get('RC_FAIL') == '0',
    'checks': {
        'orchestrator': {'ok': os.environ.get('RC_ORCH_OK') == '1', 'detail': os.environ.get('RC_ORCH_DETAIL', '')},
        'openclaw_bridge': {'ok': os.environ.get('RC_BRIDGE_OK') == '1', 'detail': os.environ.get('RC_BRIDGE_DETAIL', '')},
        'ollama_audit': {'ok': os.environ.get('RC_OLLAMA_OK') == '1', 'detail': os.environ.get('RC_OLLAMA_DETAIL', '')},
        'soe_m3_login': {'ok': os.environ.get('RC_SOE_OK') == '1', 'detail': os.environ.get('RC_SOE_DETAIL', '')},
        'soe_m3_zone': {'ok': os.environ.get('RC_ZONE_OK') == '1', 'detail': os.environ.get('RC_ZONE_DETAIL', '')},
        'soe_m5_play': {'ok': os.environ.get('RC_M5_OK') == '1', 'detail': os.environ.get('RC_M5_DETAIL', '')},
        'godot_sidecar': {'ok': os.environ.get('RC_SIDECAR_OK') == '1', 'detail': os.environ.get('RC_SIDECAR_DETAIL', '')},
        'm9_minimap': {'ok': os.environ.get('RC_M9_OK') == '1', 'detail': os.environ.get('RC_M9_DETAIL', '')},
        'autoconsult': {'ok': os.environ.get('RC_AUTO_OK') == '1', 'detail': os.environ.get('RC_AUTO_DETAIL', '')},
        'prime_udp': {'ok': os.environ.get('RC_UDP_OK') == '1', 'detail': os.environ.get('RC_UDP_DETAIL', '')},
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
"
else
  echo ""
  echo "=== Résumé reality-check équipe ==="
  for k in orchestrator openclaw_bridge ollama_audit soe_m3_login soe_m3_zone soe_m5_play godot_sidecar m9_minimap autoconsult prime_udp; do
    status="ROUGE"
    [[ "${CHECKS[${k}_ok]:-0}" == "1" ]] && status="VERT"
    echo "  ${k}: ${status} — ${CHECKS[${k}_detail]:-}"
  done
  if [[ "${FAIL}" -eq 0 ]]; then
    echo "GLOBAL: VERT"
  else
    echo "GLOBAL: ROUGE"
    exit 1
  fi
fi

if [[ "${JSON_OUT}" == "1" && "${FAIL}" -ne 0 ]]; then
  exit 1
fi
