#!/usr/bin/env bash
# M5 — Jouer en 2D (ZQSD) via SOE + prime_controller
set -euo pipefail

PRIME_HOST="${PRIME_HOST:-192.168.0.246}"
LOGIN_PORT="${LOGIN_PORT:-44553}"
GODOT_PORT="${GODOT_PORT:-12345}"
CMD_PORT="${CMD_PORT:-12346}"
USER="${SWG_USER:-Bot_IA}"
PASS="${SWG_PASS:-lbgiabot}"
CHAR="${SWG_CHAR:-0}"

CLIENT_LBG="${CLIENT_LBG:-$HOME/projects/new_mmo/client-prime-lbg}"
PRIME_CLIENT="${PRIME_CLIENT:-$HOME/projects/new_mmo/prime-client}"

if grep -qi microsoft /proc/version 2>/dev/null; then
  GODOT_HOST="${GODOT_HOST:-$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)}"
else
  GODOT_HOST="${GODOT_HOST:-127.0.0.1}"
fi

echo "== M5 play =="
echo "  Godot     : ouvrir prime-client (mode PLAY après connexion)"
echo "  SOE+ZQSD  : ${USER}@${PRIME_HOST}:${LOGIN_PORT}"
echo "  Godot UDP : ${GODOT_HOST}:${GODOT_PORT}"
echo "  Cmd UDP   : 0.0.0.0:${CMD_PORT}  (Godot → config/play_mode.json cmd_host)"
echo ""
echo "Godot Windows : cmd_host = IP WSL dans config/play_mode.json"
echo ""

cd "${CLIENT_LBG}"
export GODOT_HOST
exec python3 soe_handshake.py \
  --host "${PRIME_HOST}" --port "${LOGIN_PORT}" \
  --user "${USER}" --password "${PASS}" --char "${CHAR}" \
  --godot-port "${GODOT_PORT}" \
  --play --cmd-port "${CMD_PORT}" \
  "$@"
