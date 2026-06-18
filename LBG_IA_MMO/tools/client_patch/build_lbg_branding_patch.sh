#!/usr/bin/env bash
# Génère patch_lbg_01.tre (musique titre / branding Prime).
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"
python3 tools/client_patch/build_lbg_branding_patch.py "$@"
