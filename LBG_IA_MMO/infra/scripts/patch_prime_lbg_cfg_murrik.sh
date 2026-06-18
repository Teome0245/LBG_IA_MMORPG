#!/usr/bin/env bash
# Ajoute patch_murrik_00.tre (priorite 26) dans swgemu_live.cfg uniquement.
# user.cfg reste minimal (pas de searchTree Murrik ici).
set -euo pipefail

CLIENT_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
TRE_NAME="${MURRIK_TRE_NAME:-patch_murrik_00.tre}"
CFG="${CLIENT_DIR}/swgemu_live.cfg"

if [[ ! -f "$CFG" ]]; then
  echo "Absent: $CFG" >&2
  exit 1
fi

if grep -q "searchTree_00_26=${TRE_NAME}" "$CFG" 2>/dev/null; then
  echo "Deja present: $CFG"
  exit 0
fi

cp -f "$CFG" "${CFG}.bak_murrik"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
inserted = False
for line in lines:
    s = line.strip()
    if s.startswith("maxSearchPriority="):
        continue
    if s.startswith("searchTree_00_26=") and "murrik" in s:
        continue
    out.append(line)
    if not inserted and s == "[SharedFile]":
        out.append("\tmaxSearchPriority=26")
        out.append("\tsearchTree_00_26=${TRE_NAME}")
        inserted = True
if not inserted:
    raise SystemExit("[SharedFile] introuvable dans swgemu_live.cfg")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p)
PY

echo "OK: swgemu_live.cfg (priorite 26 = ${TRE_NAME})"
