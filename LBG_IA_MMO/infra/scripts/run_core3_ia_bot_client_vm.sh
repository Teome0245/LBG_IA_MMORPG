#!/usr/bin/env bash
# Compte reserve : Bot_IA — perso Lia Bot (headless, Serveur Prime).
# Paramétrable pour d'autres joueurs IA via CORE3_CLIENT_ENV_FILE / CORE3_CLIENT_OPTIONS_JSON.
# Ne demarre pas si le perso est deja en ligne (client SWG ou autre session).
#
# Usage (sur VM 245) :
#   bash /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
#   bash .../run_core3_ia_bot_client_vm.sh --login-only   # test auth

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN_DIR="${CORE3_BIN_DIR:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"
CLIENT="${BIN_DIR}/core3client"
SESSION_JSON="${CORE3_CLIENT_OPTIONS_JSON:-${BIN_DIR}/ia_bridge/lia_bot_session.json}"
ENV_FILE="${CORE3_CLIENT_ENV_FILE:-${BIN_DIR}/.env-core3client}"
SIDECAR_URL="${CORE3_IA_SIDECAR_URL:-http://127.0.0.1:8791}"
BOT_CHAR="${CORE3_IA_BOT_CHARACTER:-Lia}"
LOGIN_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --login-only) LOGIN_ONLY=1 ;;
  esac
done

if [[ ! -x "${CLIENT}" ]]; then
  echo "ERROR: ${CLIENT} introuvable. Build VM :" >&2
  echo "  cd /opt/lbg-new-mmo-clean/MMOCoreORB/build && cmake --build . --target core3client -j\$(nproc)" >&2
  echo "  cp build/src/client/core3client ${BIN_DIR}/" >&2
  exit 1
fi

if [[ ! -f "${SESSION_JSON}" ]]; then
  echo "ERROR: ${SESSION_JSON} manquant" >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "${ENV_FILE}" | grep -v '^\s*$' | sed 's/^/export /')
  set +a
fi

if [[ "${LOGIN_ONLY}" == "0" ]]; then
  # Snapshot != session reelle : who.json + log client (SceneReady) pour eviter fantomes sessionSeconds=0.
  online="$(python3 -c "
import json
import time
from pathlib import Path
name = '${BOT_CHAR}'.strip().lower()
bin_dir = Path('${BIN_DIR}')

def client_scene_ready() -> bool:
    log = bin_dir / 'log' / 'core3client.log'
    if not log.is_file():
        return False
    if time.time() - log.stat().st_mtime > 180:
        return False
    tail = log.read_text(encoding='utf-8', errors='replace')[-12000:]
    if 'Staying connected' not in tail or 'setSceneReady' not in tail:
        return False
    if name == 'lia' and 'Selected character: Lia' not in tail:
        return False
    if name == 'nix' and 'Character' not in tail:
        return False
    return True

if client_scene_ready():
    print('1')
    raise SystemExit

who = bin_dir / 'log' / 'who.json'
if who.is_file():
    try:
        data = json.loads(who.read_text(encoding='utf-8'))
        for c in data.get('clients') or []:
            if str(c.get('firstName', '')).strip().lower() != name:
                continue
            if int(c.get('sessionSeconds') or 0) >= 15:
                print('1')
                raise SystemExit
    except Exception:
        pass
log = bin_dir / 'log' / 'online-players.log'
if log.is_file():
    try:
        line = [ln for ln in log.read_text(encoding='utf-8', errors='replace').splitlines() if ln.strip()][-1]
        data = json.loads(line)
        for c in data.get('clients') or []:
            if str(c.get('firstName', '')).strip().lower() != name:
                continue
            if int(c.get('sessionSeconds') or 0) >= 15:
                print('1')
                raise SystemExit
    except Exception:
        pass
print('0')
" 2>/dev/null || echo 0)"
  if [[ "${online}" == "1" ]]; then
    echo "${BOT_CHAR} deja en ligne (session headless active) — core3client non lance."
    exit 0
  fi

  ready=0
  for _ in $(seq 1 90); do
    if python3 -c "
import json
from pathlib import Path
who = Path('${BIN_DIR}') / 'log' / 'who.json'
if who.is_file():
    d = json.loads(who.read_text(encoding='utf-8'))
    if d.get('isServerLoading') is True:
        raise SystemExit(1)
" 2>/dev/null; then
      if (cd "${BIN_DIR}" && timeout 14 ./core3client --env "${ENV_FILE}" --login-only 2>&1 | grep -q "Authentication successful"); then
        ready=1
        break
      fi
    fi
    sleep 5
  done
  if [[ "${ready}" != "1" ]]; then
    echo "ERROR: login ${CORE3_CLIENT_USERNAME:-?} indisponible (Prime en chargement ou port login)." >&2
    exit 102
  fi
fi

cd "${BIN_DIR}"
export CORE3_CLIENT_USERNAME="${CORE3_CLIENT_USERNAME:-Bot_IA}"
export CORE3_CLIENT_PASSWORD="${CORE3_CLIENT_PASSWORD:-${CORE3_IA_BOT_PASSWORD:-lbgiabot}}"

extra=()
if [[ "${LOGIN_ONLY}" == "1" ]]; then
  extra+=(--login-only)
fi

# Après zone-in : cantina Lia (évite relog manuel quand Prime a redémarré).
if [[ "${LOGIN_ONLY}" == "0" && "${BOT_CHAR}" == "Lia" ]]; then
  (
    sleep 40
    for _ in $(seq 1 24); do
      if tail -40 "${BIN_DIR}/log/core3client.log" 2>/dev/null | grep -q "Staying connected"; then
        printf '%s\n' 'housing_enter|Lia|tatooine|0|0|0|cantina' >> "${BIN_DIR}/ia_bridge/pending.jsonl"
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) post_zone: housing_enter cantina" >> "${BIN_DIR}/log/ia_bot_bootstrap.log"
        break
      fi
      sleep 10
    done
  ) &
fi

exec ./core3client \
  --env "${ENV_FILE}" \
  --options-json "${SESSION_JSON}" \
  "${extra[@]}"
