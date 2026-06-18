#!/usr/bin/env bash
# Génère manifest.json + copie les fichiers patchés vers infra/client-patch-server/patches/{precu,prime}/.
# Usage :
#   ./generate_client_patch_manifests.sh
#   SWG_ROOT=/mnt/j/swgemu ./generate_client_patch_manifests.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PATCH_ROOT="${ROOT_DIR}/infra/client-patch-server"
SWG_ROOT="${SWG_ROOT:-/mnt/j/swgemu}"

PRECU_GAME="${SWG_ROOT}/StarWarsGalaxies"
PRIME_GAME="${SWG_ROOT}/clients/prime-lbg"

PRECU_FILES=(
  SWGEmu.exe
  swgemu.cfg
  swgemu_login.cfg
  swgemu_live.cfg
  swgemu_preload.cfg
  user.cfg
)

PRIME_FILES=(
  swgemu.cfg
  swgemu_login.cfg
  swgemu_live.cfg
  swgemu_preload.cfg
  user.cfg
  lbgemu_client.cfg
  options.cfg
  patch_lbg_00.tre
)

die() { echo "generate_client_patch_manifests: $*" >&2; exit 1; }

md5_file() {
  md5sum "$1" | awk '{print $1}'
}

write_manifest() {
  local channel="$1"
  local version="$2"
  shift 2
  local -a names=("$@")
  local out_dir="${PATCH_ROOT}/patches/${channel}"
  local manifest="${out_dir}/manifest.json"
  local tmp
  tmp="$(mktemp)"

  {
    echo "{"
    echo "  \"version\": \"${version}\","
    echo "  \"files\": ["
    local first=1
    for name in "${names[@]}"; do
      local src="${out_dir}/${name}"
      [[ -f "${src}" ]] || die "fichier patch manquant: ${src}"
      local hash
      hash="$(md5_file "${src}")"
      if [[ "${first}" -eq 1 ]]; then first=0; else echo ","; fi
      printf '    { "name": "%s", "hash": "%s" }' "${name}" "${hash}"
    done
    echo ""
    echo "  ]"
    echo "}"
  } >"${tmp}"
  mv "${tmp}" "${manifest}"
  echo "  → ${manifest} ($(jq -r '.files | length' "${manifest}" 2>/dev/null || echo "${#names[@]}") fichiers)"
}

copy_patch_file() {
  local src="$1"
  local dest="$2"
  [[ -f "${src}" ]] || die "source introuvable: ${src}"
  mkdir -p "$(dirname "${dest}")"
  cp -f "${src}" "${dest}"
}

sync_channel() {
  local channel="$1"
  local game_dir="$2"
  shift 2
  local -a files=("$@")
  local out_dir="${PATCH_ROOT}/patches/${channel}"

  echo "Canal ${channel} ← ${game_dir}"
  mkdir -p "${out_dir}"

  for name in "${files[@]}"; do
    local src="${game_dir}/${name}"
    local dest="${out_dir}/${name}"
  if [[ "${name}" == "swgemu_login.cfg" && -f "${PATCH_ROOT}/patches/${channel}/swgemu_login.cfg" ]]; then
      # Garder le template versionné (ports 44453 / 44553) s'il existe déjà dans le dépôt.
      echo "  · ${name} (template dépôt)"
      continue
    fi
    [[ -f "${src}" ]] || die "fichier client manquant: ${src}"
    copy_patch_file "${src}" "${dest}"
    echo "  · ${name}"
  done
}

[[ -d "${PRECU_GAME}" ]] || die "PreCu introuvable: ${PRECU_GAME}"
[[ -d "${PRIME_GAME}" ]] || die "Prime introuvable: ${PRIME_GAME}"

# Prime : s'assurer que lbgemu_client.cfg existe (modèle repo si absent côté client)
if [[ ! -f "${PRIME_GAME}/lbgemu_client.cfg" ]]; then
  local_template="${ROOT_DIR}/../../new_mmo/client-prime-lbg/lbgemu_client.cfg"
  if [[ -f "${local_template}" ]]; then
    cp -f "${local_template}" "${PRIME_GAME}/lbgemu_client.cfg"
    echo "Copié lbgemu_client.cfg depuis new_mmo vers ${PRIME_GAME}"
  fi
fi

# Prime : patch /lbgwe (World Editor) — regénérer si absent
if [[ ! -f "${PATCH_ROOT}/patches/prime/patch_lbg_00.tre" ]]; then
  echo "Génération patch_lbg_00.tre (première fois)..."
  bash "${ROOT_DIR}/tools/client_patch/build_lbgwe_client_patch.sh"
fi

# Prime : branding (musique titre) — regénérer si absent
if [[ ! -f "${PATCH_ROOT}/patches/prime/patch_lbg_01.tre" ]]; then
  echo "Génération patch_lbg_01.tre (branding / musique login)..."
  bash "${ROOT_DIR}/tools/client_patch/build_lbg_branding_patch.sh"
fi

sync_channel precu "${PRECU_GAME}" "${PRECU_FILES[@]}"
write_manifest precu "precu-$(date +%Y%m%d)" "${PRECU_FILES[@]}"

sync_channel prime "${PRIME_GAME}" "${PRIME_FILES[@]}"
write_manifest prime "prime-$(date +%Y%m%d)" "${PRIME_FILES[@]}"
if [[ -f "${PRECU_GAME}/swgemu_login.cfg" ]]; then
  cp -f "${PATCH_ROOT}/patches/precu/swgemu_login.cfg" "${PRECU_GAME}/swgemu_login.cfg"
  echo "Port PreCu corrigé sur ${PRECU_GAME}/swgemu_login.cfg (44453)"
fi

echo "OK — déployer sur VM 245 : infra/scripts/install_client_patch_server_245.sh"
