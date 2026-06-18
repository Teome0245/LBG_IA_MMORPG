#!/usr/bin/env bash
# Lance murrik_texture_dds_to_dds.ps1 sur Windows (Agent_IA + ComfyUI doivent tourner).
#
# Usage:
#   export LBG_DESKTOP_BASE_URL="http://192.168.0.10:5005"
#   export LBG_DESKTOP_APPROVAL="CHANGE-MOI"
#   ./run_murrik_texture_dds_pipeline_wsl.sh \
#     "/mnt/j/swgemu/MOD_LBG/texture/bth_f_face.dds" \
#     "/mnt/j/swgemu/MOD_LBG/texture/bth_f_face.dds"
#
# Optionnel:
#   TEXTURE_KIND=face|body|auto
#   SEED=42
#   DENOISE=0.18

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PS1_WIN="$(wslpath -w "${SCRIPT_DIR}/murrik_texture_dds_to_dds.ps1")"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <input.dds> <output.dds>" >&2
  exit 2
fi

IN_WIN="$(wslpath -w "$1")"
OUT_WIN="$(wslpath -w "$2")"

_wsl_nameserver_host() {
  grep -m1 '^nameserver[[:space:]]' /etc/resolv.conf 2>/dev/null | awk '{print $2}' || true
}

if [[ -n "${LBG_DESKTOP_BASE_URL:-}" ]]; then
  BASE_URL="$LBG_DESKTOP_BASE_URL"
else
  _h="$(_wsl_nameserver_host)"
  BASE_URL="${_h:+http://${_h}:5005}"
  BASE_URL="${BASE_URL:-http://192.168.0.10:5005}"
fi

APPROVAL="${LBG_DESKTOP_APPROVAL:-}"
TEXTURE_KIND="${TEXTURE_KIND:-auto}"
SEED="${SEED:-0}"
DENOISE="${DENOISE:--1}"

POWERSHELL="${POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"

ARGS=(
  -NoProfile -ExecutionPolicy Bypass -File "$PS1_WIN"
  -InputDds "$IN_WIN"
  -OutputDds "$OUT_WIN"
  -BaseUrl "$BASE_URL"
  -TextureKind "$TEXTURE_KIND"
  -Seed "$SEED"
  -Denoise "$DENOISE"
)

if [[ -n "$APPROVAL" ]]; then
  ARGS+=( -Approval "$APPROVAL" )
fi

echo "[run_murrik_texture_dds_pipeline_wsl] $IN_WIN -> $OUT_WIN"
exec "$POWERSHELL" "${ARGS[@]}"
