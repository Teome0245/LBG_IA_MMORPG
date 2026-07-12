#!/usr/bin/env bash
# Smoke LAN — SOE M3 login only (client-prime-lbg).
set -euo pipefail

CLIENT_PRIME="${LBG_CLIENT_PRIME_LBG_DIR:-/home/sdesh/projects/new_mmo/client-prime-lbg}"
HOST="${LBG_SOE_HOST:-192.168.0.246}"
PORT="${LBG_SOE_LOGIN_PORT:-44553}"
USER="${LBG_SOE_USER:-Bot_IA}"
PASS="${LBG_SOE_PASSWORD:-lbgiabot}"
TIMEOUT="${LBG_SOE_M3_LOGIN_TIMEOUT_S:-95}"

echo "=== Smoke SOE M3 login (${HOST}:${PORT}) ==="
[[ -f "${CLIENT_PRIME}/soe_handshake.py" ]] || { echo "soe_handshake.py absent" >&2; exit 1; }

set +e
OUT=$(timeout "${TIMEOUT}" python3 "${CLIENT_PRIME}/soe_handshake.py" \
  --host "${HOST}" --port "${PORT}" --user "${USER}" --password "${PASS}" --no-zone 2>&1)
RC=$?
set -e
echo "${OUT}" | tail -20
echo "${OUT}" | grep -qE "\[Login\] OK connexion LoginServer terminee|\[LoginClientToken\]" || {
  echo "ECHEC login SOE (rc=${RC})" >&2
  exit 1
}
echo "OK SOE M3 login"
