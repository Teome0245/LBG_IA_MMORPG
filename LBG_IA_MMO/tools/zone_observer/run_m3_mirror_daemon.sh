#!/usr/bin/env bash
# M3 daemon — boucle continue (systemd ou nohup). Ne pas relancer à la main toutes les 5 min.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${M3_MIRROR_ENV:-${ROOT}/infra/config/m3_mirror.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

export PRIME_HOST="${PRIME_HOST:-192.168.0.246}"
export PRIME_USER="${PRIME_USER:-lbg}"
export GODOT_PORT="${GODOT_PORT:-12345}"
export PRIME_CLIENT="${PRIME_CLIENT:-$HOME/projects/new_mmo/prime-client}"
export TRACK_PLAYERS="${TRACK_PLAYERS:-Lia,Nix,Mira,Gally,Teome}"
export MIRROR_PLAYERS_ONLY="${MIRROR_PLAYERS_ONLY:-false}"

if [[ -z "${GODOT_HOST:-}" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  export GODOT_HOST="$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)"
fi

exec python3 "${ROOT}/tools/zone_observer/zone_feed.py" \
  --mirror \
  --quiet \
  --godot-port "${GODOT_PORT}" \
  --godot-host "${GODOT_HOST:-127.0.0.1}" \
  --prime-host "${PRIME_HOST}" \
  --prime-user "${PRIME_USER}" \
  --local-bridge-dir "${PRIME_CLIENT}/cache" \
  --json-out "${PRIME_CLIENT}/cache/zone_feed.json" \
  --track-players "${TRACK_PLAYERS}" \
  $([[ "${MIRROR_PLAYERS_ONLY}" == "true" ]] && echo --players-only)
