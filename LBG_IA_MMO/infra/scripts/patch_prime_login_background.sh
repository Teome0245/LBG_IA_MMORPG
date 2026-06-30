#!/usr/bin/env bash
# Remplace l'écran login Aurora (new_login_screen) par l'UI classique + fond LBG.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
SOURCES_DIR="${CUSTOM_BRANDING_SOURCES:-/mnt/j/swgemu/custom_branding_sources}"
TRE_LOGIN="${PRIME_DIR}/patch_prime_login_00.tre"
CFG="${PRIME_DIR}/swgemu_live.cfg"

if [[ ! -d "${PRIME_DIR}" ]]; then
  echo "ERROR: dossier Prime absent: ${PRIME_DIR}" >&2
  exit 1
fi

python3 "${ROOT_DIR}/tools/client_patch/build_prime_login_branding.py" \
  --prime-dir "${PRIME_DIR}" \
  --sources-dir "${SOURCES_DIR}" \
  --out "${TRE_LOGIN}"

cp -a "${CFG}" "${CFG}.bak_login_lbg"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out, seen100, seen99 = [], False, False
for line in lines:
    s = line.strip()
    if s.startswith("maxSearchPriority="):
        out.append("\tmaxSearchPriority=100")
        continue
    if s.startswith("searchTree_00_100="):
        if not seen100:
            out.append("\tsearchTree_00_100=patch_prime_login_00.tre")
            seen100 = True
        continue
    if s.startswith("searchTree_00_99=") and "patch_prime_ui" in s:
        if not seen99:
            out.append("\tsearchTree_00_99=patch_prime_ui_fr_00.tre")
            seen99 = True
        continue
    out.append(line)

if not seen100:
    injected = []
    for line in out:
        injected.append(line)
        if line.strip().startswith("maxSearchPriority="):
            injected.append("\tsearchTree_00_100=patch_prime_login_00.tre")
            seen100 = True
    out = injected

p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p)
PY

# Casque 3D login (patch_11_03) — optionnel, souvent déjà appliqué
if [[ -f "${ROOT_DIR}/tools/client_patch/patch_prime_vanilla_branding.py" ]]; then
  python3 "${ROOT_DIR}/tools/client_patch/patch_prime_vanilla_branding.py" \
    --prime-dir "${PRIME_DIR}" --step 1 >/dev/null 2>&1 || true
fi

echo ""
echo "OK — relancer lbgemu.exe (Prime)."
echo "  Sources      : ${SOURCES_DIR}"
echo "  Priorité 100 : patch_prime_login_00.tre (UI + textures custom)"
echo "  Priorité 99  : patch_prime_ui_fr_00.tre (libellés FR)"
echo "  Backup cfg   : ${CFG}.bak_login_lbg"
echo ""
echo "Après modification des .dds/.inc dans custom_branding_sources, relancer ce script."
