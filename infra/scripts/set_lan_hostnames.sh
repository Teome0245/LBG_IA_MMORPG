#!/usr/bin/env bash
# Raccourci racine LBG_IA_MMORPG → LBG_IA_MMO/infra/scripts/set_lan_hostnames.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT}/LBG_IA_MMO/infra/scripts/set_lan_hostnames.sh" "$@"
