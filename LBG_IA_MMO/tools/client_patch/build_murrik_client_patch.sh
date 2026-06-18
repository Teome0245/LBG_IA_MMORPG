#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="${MOD_LBG_ROOT:-/mnt/j/swgemu/MOD_LBG}"
OUT_TRE="${MURRIK_TRE_OUT:-/mnt/j/swgemu/clients/prime-lbg/patch_murrik_00.tre}"
META="${ROOT}/infra/client-patch-server/patches/prime/patch_murrik_00.json"

python3 "${ROOT}/tools/client_patch/build_murrik_client_patch.py" \
  --source "$SOURCE" \
  --output-tre "$OUT_TRE" \
  --metadata-json "$META"

echo "OK: $OUT_TRE"
