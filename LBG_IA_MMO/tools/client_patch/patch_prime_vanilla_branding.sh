#!/usr/bin/env bash
# Branding Prime in-place : patch_11_03.tre (login) + data_music_00.tre (titre).
# Backup automatique : *.tre.bak.lbg — PreCu (StarWarsGalaxies) non touché.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_DIR:-/mnt/j/swgemu/clients/prime-lbg}"
cd "${ROOT_DIR}"
python3 tools/client_patch/patch_prime_vanilla_branding.py --prime-dir "${PRIME_DIR}" "$@"
