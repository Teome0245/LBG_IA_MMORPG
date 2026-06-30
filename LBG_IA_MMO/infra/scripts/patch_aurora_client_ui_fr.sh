#!/usr/bin/env bash
# Corrige l'écran login Aurora ([UI]:CPT_LOGIN) : TRE FR + ui_loginscreen.inc.
#
# Usage :
#   bash infra/scripts/patch_aurora_client_ui_fr.sh
#   AURORA_CLIENT_DIR=/mnt/j/swgemu/StarWarsGalaxies\ -\ AURORA bash infra/scripts/patch_aurora_client_ui_fr.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AURORA_DIR="${AURORA_CLIENT_DIR:-/mnt/j/swgemu/StarWarsGalaxies - AURORA}"
PATCH_FR_SRC="${PATCH_FR_SRC:-/mnt/j/swgemu/clients/prime-lbg/patch_fr_00.tre}"
CFG="${AURORA_DIR}/swgemu_live.cfg"
TRE_FIX="${AURORA_DIR}/patch_aurora_ui_fr_00.tre"
TRE_FR="${AURORA_DIR}/patch_fr_00.tre"

if [[ ! -d "${AURORA_DIR}" ]]; then
  echo "ERROR: répertoire Aurora absent : ${AURORA_DIR}" >&2
  exit 1
fi

if [[ ! -f "${PATCH_FR_SRC}" ]]; then
  echo "ERROR: patch_fr source absent : ${PATCH_FR_SRC}" >&2
  exit 1
fi

if [[ ! -f "${TRE_FR}" ]]; then
  echo "Copie ${PATCH_FR_SRC} → ${TRE_FR}"
  cp -a "${PATCH_FR_SRC}" "${TRE_FR}"
fi

python3 "${ROOT_DIR}/tools/client_patch/build_aurora_login_ui_fix.py" \
  --aurora-dir "${AURORA_DIR}" \
  --patch-fr "${PATCH_FR_SRC}" \
  --out "${TRE_FIX}"

if [[ ! -f "${CFG}" ]]; then
  echo "ERROR: ${CFG} absent" >&2
  exit 1
fi

cp -a "${CFG}" "${CFG}.bak_ui_fr"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen_99 = seen_98 = seen_85_1 = False
for line in lines:
    s = line.strip()
    if s.startswith("searchTree_00_99="):
        if not seen_99:
            out.append("\tsearchTree_00_99=patch_aurora_ui_fr_00.tre")
            seen_99 = True
        continue
    if s.startswith("searchTree_00_98=") and "client.tre" in s:
        if not seen_98:
            out.append("\tsearchTree_00_98=patch_fr_00.tre")
            out.append("\tsearchTree_00_97=client.tre")
            seen_98 = True
        continue
    if s.startswith("searchTree_00_85=ILM_aurora_1"):
        if not seen_85_1:
            out.append("\tsearchTree_00_85=ILM_aurora_1.tre")
            out.append("\tsearchTree_01_85=ILM_aurora_2.tre")
            seen_85_1 = True
        continue
    if s.startswith("searchTree_00_85=ILM_aurora_2"):
        continue
    if s.startswith("searchTree_00_89=Aur_French"):
        out.append("\tsearchTree_00_96=Aur_French.tre")
        continue
    out.append(line)

if not seen_99:
    # inject after maxSearchPriority block
    injected = []
    for line in out:
        injected.append(line)
        if line.strip().startswith("maxSearchPriority="):
            injected.append("\tsearchTree_00_99=patch_aurora_ui_fr_00.tre")
            injected.append("\tsearchTree_00_98=patch_fr_00.tre")
            injected.append("\tsearchTree_00_97=client.tre")
            injected.append("\tsearchTree_00_96=Aur_French.tre")
            seen_99 = True
    out = injected

# Désactive MOTD (souvent EN / cassé)
out2 = []
for line in out:
    if line.strip().startswith("messageOfTheDayTable="):
        out2.append("\t# messageOfTheDayTable=live_motd")
        continue
    out2.append(line)

p.write_text("\n".join(out2) + "\n", encoding="utf-8")
print("Patched:", p)
PY

echo ""
echo "OK — relancer le client Aurora."
echo "  Priorité 99 : patch_aurora_ui_fr_00.tre (STF FR + alias CPT_LOGIN)"
echo "  Priorité 98 : patch_fr_00.tre"
echo "  Backup cfg  : ${CFG}.bak_ui_fr"
