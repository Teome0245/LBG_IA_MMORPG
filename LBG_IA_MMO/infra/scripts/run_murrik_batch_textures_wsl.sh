#!/usr/bin/env bash
# Genere les 4 textures Murrik principales (face/body F/M) via pipeline DDS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPE="${SCRIPT_DIR}/run_murrik_texture_dds_pipeline_wsl.sh"
TEXTURE_DIR="${MURRIK_TEXTURE_DIR:-/mnt/j/swgemu/MOD_LBG/texture}"
BACKUP_DIR="${MURRIK_TEXTURE_BACKUP:-/mnt/j/swgemu/MOD_LBG/texture_backup_vanilla}"

export LBG_DESKTOP_BASE_URL="${LBG_DESKTOP_BASE_URL:-http://192.168.0.10:5005}"
export LBG_DESKTOP_APPROVAL="${LBG_DESKTOP_APPROVAL:-CHANGE-MOI}"

mkdir -p "$BACKUP_DIR"

process_one() {
  local name="$1"
  local kind="$2"
  local dds="${TEXTURE_DIR}/${name}"
  if [[ ! -f "$dds" ]]; then
    echo "SKIP (absent): $dds" >&2
    return 0
  fi
  if [[ ! -f "${BACKUP_DIR}/${name}" ]]; then
    cp -f "$dds" "${BACKUP_DIR}/${name}"
    echo "Backup: ${BACKUP_DIR}/${name}"
  fi
  echo "== Pipeline: $name (kind=$kind) =="
  TEXTURE_KIND="$kind" "$PIPE" "$dds" "$dds"
}

process_one "bth_f_face.dds" "face"
process_one "bth_m_face.dds" "face"
process_one "bth_f_body.dds" "body"
process_one "bth_m_body.dds" "body"

echo "OK: textures principales Murrik"
