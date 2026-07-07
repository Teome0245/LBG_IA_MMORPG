#!/usr/bin/env bash
# Login Prime : ui_loginscreen vanilla (029) + écran chargement vanilla forcé.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
SOURCES_DIR="${CUSTOM_BRANDING_SOURCES:-/mnt/j/swgemu/custom_branding_sources}"
TRE_LOGIN="${PRIME_DIR}/patch_prime_login_00.tre"
CFG="${PRIME_DIR}/swgemu_live.cfg"
ARCHIVE_DIR="${PRIME_DIR}/_archived_patch_lbg"
TRASH_DIR="/mnt/j/swgemu/_trash_patch_lbg_$(date +%Y%m%d)"
EXTRA_ARGS=()
[[ "${INCLUDE_LOADING:-0}" == "1" ]] && EXTRA_ARGS+=(--include-loading)
[[ "${INCLUDE_SPLASH:-0}" == "1" ]] && EXTRA_ARGS+=(--include-splash)

if [[ ! -d "${PRIME_DIR}" ]]; then
  echo "ERROR: dossier Prime absent: ${PRIME_DIR}" >&2
  exit 1
fi

python3 "${ROOT_DIR}/tools/client_patch/build_prime_login_branding.py" \
  --prime-dir "${PRIME_DIR}" \
  --sources-dir "${SOURCES_DIR}" \
  --out "${TRE_LOGIN}" \
  "${EXTRA_ARGS[@]}"

mkdir -p "${TRASH_DIR}"
if [[ -d "${ARCHIVE_DIR}" ]]; then
  mv -f "${ARCHIVE_DIR}"/* "${TRASH_DIR}/" 2>/dev/null || true
  rmdir "${ARCHIVE_DIR}" 2>/dev/null || true
  echo "patch_lbg archivé hors client → ${TRASH_DIR}"
fi
for f in patch_lbg_00.tre patch_lbg_01.tre; do
  if [[ -f "${PRIME_DIR}/${f}" ]]; then
    mv -f "${PRIME_DIR}/${f}" "${TRASH_DIR}/"
    echo "Retiré: ${f}"
  fi
done
rm -f "${PRIME_DIR}/swgemu_machineoptions.iff" "${PRIME_DIR}/misc/cache"*.iff 2>/dev/null || true

# Locale FR (options.cfg auto-généré écrase parfois user.cfg)
if [[ -f "${PRIME_DIR}/options.cfg" ]]; then
  sed -i 's/defaultLocale=en/defaultLocale=fr/' "${PRIME_DIR}/options.cfg"
  sed -i 's/fontLocale=en/fontLocale=fr/' "${PRIME_DIR}/options.cfg"
fi

cp -a "${CFG}" "${CFG}.bak_login_lbg"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen_login = seen_ui_fr = False
for line in lines:
    s = line.strip()
    if s.startswith("maxSearchPriority="):
        out.append("\tmaxSearchPriority=99")
        continue
    if "patch_lbg" in s and s.startswith("searchTree_"):
        continue
    if s.startswith("searchTree_00_100="):
        continue
    if s.startswith("searchTree_00_99=") and "patch_prime_login" in s:
        if not seen_login:
            out.append("\tsearchTree_00_99=patch_prime_login_00.tre")
            seen_login = True
        continue
    if s.startswith("searchTree_01_99=") and "patch_prime_ui" in s:
        if not seen_ui_fr:
            out.append("\tsearchTree_01_99=patch_prime_ui_fr_00.tre")
            seen_ui_fr = True
        continue
    if s.startswith("searchTree_00_99=") and "patch_prime_ui" in s:
        if not seen_ui_fr:
            out.append("\tsearchTree_01_99=patch_prime_ui_fr_00.tre")
            seen_ui_fr = True
        continue
    if s == "searchTree_00_55=LBG_patch_026.tre":
        out.append("\tsearchTree_00_55=LBG_patch_026.tre  # assets Aurora (login → patch_prime 99)")
        continue
    if s.startswith("# searchTree_00_55=LBG_patch_026.tre"):
        out.append("\tsearchTree_00_55=LBG_patch_026.tre  # assets Aurora (login → patch_prime 99)")
        continue
    out.append(line)

if not seen_login:
    injected = []
    for line in out:
        injected.append(line)
        if line.strip().startswith("maxSearchPriority="):
            injected.append("\tsearchTree_00_99=patch_prime_login_00.tre")
            seen_login = True
    out = injected
if not seen_ui_fr:
    for i, line in enumerate(out):
        if "searchTree_00_99=patch_prime_login_00.tre" in line:
            out.insert(i + 1, "\tsearchTree_01_99=patch_prime_ui_fr_00.tre")
            seen_ui_fr = True
            break

p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p)
PY

echo ""
echo "OK — relancer lbgemu.exe (Prime)."
echo "  Login        : LBG_patch_029 via patch_prime_login_00.tre (fond Aurora = 026)"
