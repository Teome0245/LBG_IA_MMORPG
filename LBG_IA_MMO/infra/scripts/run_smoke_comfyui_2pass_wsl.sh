#!/usr/bin/env bash
# Lance smoke_comfyui_2pass.ps1 depuis WSL via PowerShell Windows.
# Les workflows du repo sont convertis en chemins Windows (\\wsl.localhost\...) lisibles par pwsh.
#
# Usage :
#   ./run_smoke_comfyui_2pass_wsl.sh
#   LBG_DESKTOP_BASE_URL=http://192.168.0.10:5005 LBG_DESKTOP_APPROVAL=SECRET ./run_smoke_comfyui_2pass_wsl.sh
#
# Variables optionnelles :
#   LBG_DESKTOP_BASE_URL   URL du worker Agent_IA (défaut : http://<nameserver resolv.conf>:5005)
#   LBG_DESKTOP_APPROVAL   Token si approval actif
#   COMFY_INPUT_DIR        -ComfyInputDir (défaut Windows du .ps1)
#   COMFY_OUTPUT_DIR       -ComfyOutputDir
#   WF_PASS1 / WF_PASS2    chemins absolus WSL vers les JSON si tu ne veux pas ceux du repo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# infra/scripts → ../../../ = racine du dépôt (parent de LBG_IA_MMO/)
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PS1_WIN="$(wslpath -w "${SCRIPT_DIR}/smoke_comfyui_2pass.ps1")"

_wsl_nameserver_host() {
  grep -m1 '^nameserver[[:space:]]' /etc/resolv.conf 2>/dev/null | awk '{print $2}' || true
}

if [[ -n "${LBG_DESKTOP_BASE_URL:-}" ]]; then
  BASE_URL="$LBG_DESKTOP_BASE_URL"
else
  _h="$(_wsl_nameserver_host)"
  if [[ -n "${_h}" ]]; then
    BASE_URL="http://${_h}:5005"
    echo "[run_smoke_comfyui_2pass_wsl] LBG_DESKTOP_BASE_URL non défini → ${BASE_URL} (hôte Windows WSL2)"
  else
    BASE_URL="http://127.0.0.1:5005"
    echo "[run_smoke_comfyui_2pass_wsl] ATTENTION : impossible de deviner l'hôte Windows ; ${BASE_URL} (souvent faux depuis WSL — exporte LBG_DESKTOP_BASE_URL)" >&2
  fi
fi

if [[ -n "${WF_PASS1:-}" ]]; then
  WF1_WIN="$(wslpath -w "${WF_PASS1}")"
else
  WF1_WIN="$(wslpath -w "${REPO_ROOT}/Boite à idées/Map_mmo.json")"
fi
if [[ -n "${WF_PASS2:-}" ]]; then
  WF2_WIN="$(wslpath -w "${WF_PASS2}")"
else
  WF2_WIN="$(wslpath -w "${REPO_ROOT}/Boite à idées/Map_mmo_pass2_buildings.json")"
fi

POWERSHELL="${POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"
if [[ ! -x "$POWERSHELL" ]]; then
  echo "PowerShell introuvable : $POWERSHELL" >&2
  exit 1
fi

ARGS=(
  -NoProfile
  -ExecutionPolicy
  Bypass
  -File
  "$PS1_WIN"
  -BaseUrl
  "$BASE_URL"
  -WorkflowPass1Path
  "$WF1_WIN"
  -WorkflowPass2Path
  "$WF2_WIN"
)

if [[ -n "${LBG_DESKTOP_APPROVAL:-}" ]]; then
  ARGS+=( -Approval "$LBG_DESKTOP_APPROVAL" )
fi
if [[ -n "${COMFY_INPUT_DIR:-}" ]]; then
  ARGS+=( -ComfyInputDir "$COMFY_INPUT_DIR" )
fi
if [[ -n "${COMFY_OUTPUT_DIR:-}" ]]; then
  ARGS+=( -ComfyOutputDir "$COMFY_OUTPUT_DIR" )
fi

echo "[run_smoke_comfyui_2pass_wsl] Pass1: $WF1_WIN"
echo "[run_smoke_comfyui_2pass_wsl] Pass2: $WF2_WIN"
exec "$POWERSHELL" "${ARGS[@]}"
