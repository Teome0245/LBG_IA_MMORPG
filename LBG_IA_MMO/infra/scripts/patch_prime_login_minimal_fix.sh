#!/usr/bin/env bash
# Correctif login minimal : champs cliquables + libellés FR (base vanilla patch_00).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
VANILLA_REF="${VANILLA_REF:-/mnt/j/swgemu/StarWarsGalaxies}"
TRE_FIX="${PRIME_DIR}/patch_prime_login_fix_00.tre"
USER_CFG="${PRIME_DIR}/user.cfg"

python3 "${ROOT_DIR}/tools/client_patch/build_prime_login_minimal_fix.py" \
  --client-dir "${PRIME_DIR}" \
  --vanilla-ref "${VANILLA_REF}" \
  --out "${TRE_FIX}"

cp -a "${USER_CFG}" "${USER_CFG}.bak_minimal_fix"

python3 <<PY
from pathlib import Path
p = Path("${USER_CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out, seen_fix, seen_fr = [], False, False
for line in lines:
    s = line.strip()
    if s.startswith("searchTree_00_25="):
        if not seen_fix:
            out.append("\tsearchTree_00_25=patch_prime_login_fix_00.tre")
            seen_fix = True
        continue
    if s.startswith("searchTree_00_24=") and "patch_fr" in s:
        if not seen_fr:
            out.append("\tsearchTree_00_24=patch_fr_00.tre")
            seen_fr = True
        continue
    out.append(line)
if not seen_fix:
    inserted = []
    in_shared = False
    for line in out:
        inserted.append(line)
        if line.strip() == "[SharedFile]":
            in_shared = True
            continue
        if in_shared and line.strip().startswith("searchTree_"):
            inserted.insert(-1, "\tsearchTree_00_25=patch_prime_login_fix_00.tre")
            seen_fix = True
            in_shared = False
    if not seen_fix:
        for i, line in enumerate(inserted):
            if line.strip() == "[SharedFile]":
                inserted.insert(i + 1, "\tsearchTree_00_25=patch_prime_login_fix_00.tre")
                seen_fix = True
                break
    out = inserted
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p)
PY

echo ""
echo "OK — relancer lbgemu.exe (Prime)."
echo "  Correctif : patch_prime_login_fix_00.tre (prio 25)"
echo "  Cause     : calque blur Selectable=true bloquait la saisie"
