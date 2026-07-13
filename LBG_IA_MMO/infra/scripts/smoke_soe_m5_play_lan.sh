#!/usr/bin/env bash
# Smoke LAN — SOE M5 play court (prime_controller, timeout).
set -euo pipefail

CLIENT_PRIME="${LBG_CLIENT_PRIME_LBG_DIR:-/home/sdesh/projects/new_mmo/client-prime-lbg}"
HOST="${LBG_SOE_HOST:-192.168.0.246}"
PORT="${LBG_SOE_LOGIN_PORT:-44553}"
USER="${LBG_SOE_USER:-Bot_IA}"
PASS="${LBG_SOE_PASSWORD:-lbgiabot}"
CHAR_NAME="${LBG_SOE_CHAR_NAME:-Lia}"
TIMEOUT="${LBG_SOE_M5_PLAY_TIMEOUT_S:-55}"

echo "=== Smoke SOE M5 play (${HOST}, timeout ${TIMEOUT}s) ==="
[[ -f "${CLIENT_PRIME}/soe_handshake.py" ]] || { echo "soe_handshake.py absent" >&2; exit 1; }

set +e
OUT=$(timeout "${TIMEOUT}" python3 "${CLIENT_PRIME}/soe_handshake.py" \
  --host "${HOST}" --port "${PORT}" --user "${USER}" --password "${PASS}" \
  --char-name "${CHAR_NAME}" \
  --play-only --godot-port 0 --cmd-port 12346 2>&1)
RC=$?
set -e
echo "${OUT}" | tail -25
if echo "${OUT}" | grep -qE "Contrôleur actif|\[--play\] Contrôleur actif"; then
  echo "OK SOE M5 play (rc=${RC})"
  exit 0
fi
echo "ECHEC SOE M5 (rc=${RC})" >&2
exit 1
