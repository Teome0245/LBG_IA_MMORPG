#!/usr/bin/env bash
# M3 — Mirroring bots IA Prime (Lia / Nix / Mira) → Godot 2D
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_CLIENT="${PRIME_CLIENT:-$HOME/projects/new_mmo/prime-client}"
PRIME_HOST="${PRIME_HOST:-192.168.0.246}"
PRIME_USER="${PRIME_USER:-lbg}"
CACHE="${PRIME_CLIENT_CACHE:-${PRIME_CLIENT}/cache}"
GODOT_PORT="${GODOT_PORT:-12345}"
TRACK="${TRACK_PLAYERS:-Lia,Nix,Mira}"

# WSL → Godot Windows : IP hôte (sinon UDP part dans le vide)
if [[ -z "${GODOT_HOST:-}" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  GODOT_HOST="$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)"
fi
GODOT_HOST="${GODOT_HOST:-127.0.0.1}"

mkdir -p "${CACHE}"

echo "== M3 mirror (bots IA Prime) =="
echo "  UDP Godot  : ${GODOT_HOST}:${GODOT_PORT}"
echo "  JSON cache : ${CACHE}/zone_feed.json"
echo "  joueurs    : ${TRACK}"
echo "  VM Prime   : ${PRIME_USER}@${PRIME_HOST}"
echo ""
echo "1) Godot Windows : godot4 --path ${PRIME_CLIENT}"
echo "2) Ce script doit tourner EN MEME TEMPS que Godot"
echo "   F1=Lia  F2=Nix  F3=Mira  (ronds verts, pas SWG_Client)"
echo ""

export PRIME_CLIENT PRIME_CLIENT_CACHE="${CACHE}" LOCAL_BRIDGE_DIR="${CACHE}"
exec python3 "${ROOT}/tools/zone_observer/zone_feed.py" \
  --mirror \
  --godot-port "${GODOT_PORT}" \
  --godot-host "${GODOT_HOST}" \
  --prime-host "${PRIME_HOST}" \
  --prime-user "${PRIME_USER}" \
  --local-bridge-dir "${CACHE}" \
  --json-out "${CACHE}/zone_feed.json" \
  --track-players "${TRACK}" \
  "$@"
