#!/usr/bin/env bash
# Raccourci WSL : même invocation que les workflows sous C:\Agent_IA\ (pas le repo Linux).
# Optionnel : LBG_DESKTOP_BASE_URL, LBG_DESKTOP_APPROVAL

set -euo pipefail

BASE_URL="${LBG_DESKTOP_BASE_URL:-http://192.168.0.10:5005}"
APPROVAL="${LBG_DESKTOP_APPROVAL:-CHANGE-MOI}"
COMFY_IN="${COMFY_INPUT_DIR:-C:/Users/sdesh/ComfyUI/input}"
COMFY_OUT="${COMFY_OUTPUT_DIR:-C:/Users/sdesh/ComfyUI/output}"

exec /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
  -NoProfile \
  -ExecutionPolicy Bypass \
  -File "C:/Agent_IA/smoke_comfyui_2pass.ps1" \
  -BaseUrl "$BASE_URL" \
  -Approval "$APPROVAL" \
  -WorkflowPass1Path "C:/Agent_IA/workflows/Map_mmo.json" \
  -WorkflowPass2Path "C:/Agent_IA/workflows/Map_mmo_pass2_buildings.json" \
  -ComfyInputDir "$COMFY_IN" \
  -ComfyOutputDir "$COMFY_OUT" \
  -Pass1OutputAsInputName "bourg.png" \
  -SeedPass1 42 \
  -SeedPass2 43
