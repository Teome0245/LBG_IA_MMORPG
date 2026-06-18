#!/usr/bin/env bash
# Active patch_fr_merged_00.tre (fusion patch_fr + Aur_French) à la place de patch_fr_00.tre.
set -euo pipefail

CLIENT_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
TRE_NAME="${FR_MERGED_TRE_NAME:-patch_fr_merged_00.tre}"
OLD_NAME="${FR_OLD_TRE_NAME:-patch_fr_00.tre}"
CFG="${CLIENT_DIR}/swgemu_live.cfg"

if [[ ! -f "${CLIENT_DIR}/${TRE_NAME}" ]]; then
  echo "Absent: ${CLIENT_DIR}/${TRE_NAME}" >&2
  echo "Générer avec: python3 tools/client_patch/merge_fr_tre.py" >&2
  exit 1
fi

if [[ ! -f "$CFG" ]]; then
  echo "Absent: $CFG" >&2
  exit 1
fi

cp -f "$CFG" "${CFG}.bak_fr_merged"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
tre = "${TRE_NAME}"
old = "${OLD_NAME}"
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen = False
for line in lines:
    s = line.strip()
    if s.startswith("searchTree_00_24=") and (old in s or tre in s or "patch_fr" in s):
        if not seen:
            out.append(f"\tsearchTree_00_24={tre}")
            seen = True
        continue
    out.append(line)
if not seen:
    raise SystemExit("searchTree_00_24 introuvable — ajouter manuellement")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p, "->", tre)
PY

echo "OK: ${CFG} utilise ${TRE_NAME} (priorité 24)"
