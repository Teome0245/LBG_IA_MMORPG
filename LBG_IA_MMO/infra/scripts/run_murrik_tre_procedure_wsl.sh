#!/usr/bin/env bash
# Procedure complete Murrik: textures (ComfyUI) -> TRE -> prime-lbg + cfg
#
#   export LBG_DESKTOP_APPROVAL="CHANGE-MOI"
#   bash LBG_IA_MMO/infra/scripts/run_murrik_tre_procedure_wsl.sh
#
# Variables:
#   SKIP_TEXTURE_PIPELINE=1  — ne pas regenere les 4 DDS (deja fait)
#   SKIP_CFG_PATCH=1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "== 0) Sync Agent_IA (scripts pipeline) =="
bash "${ROOT}/infra/scripts/sync_windows_agent.sh" || true

if [[ "${SKIP_TEXTURE_PIPELINE:-0}" != "1" ]]; then
  echo "== 1) Textures Murrik (face/body F/M) via ComfyUI =="
  bash "${SCRIPT_DIR}/run_murrik_batch_textures_wsl.sh"
else
  echo "== 1) SKIP textures (SKIP_TEXTURE_PIPELINE=1) =="
fi

echo "== 2) Build patch_murrik_00.tre =="
bash "${ROOT}/tools/client_patch/build_murrik_client_patch.sh"

if [[ "${SKIP_CFG_PATCH:-0}" != "1" ]]; then
  echo "== 3) Patch swgemu_live.cfg / user.cfg =="
  bash "${SCRIPT_DIR}/patch_prime_lbg_cfg_murrik.sh"
else
  echo "== 3) SKIP cfg =="
fi

echo ""
echo "TERMINE."
echo "  TRE: /mnt/j/swgemu/clients/prime-lbg/patch_murrik_00.tre"
echo "  Relance le client Prime (hard restart)."
