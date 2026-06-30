#!/usr/bin/env bash
# Libellés login Prime (USERNAME, CPT_LOGIN…) — STF FR + alias majuscules, sans toucher ui_loginscreen.inc.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
TRE_FIX="${PRIME_DIR}/patch_prime_ui_fr_00.tre"
CFG="${PRIME_DIR}/swgemu_live.cfg"

python3 "${ROOT_DIR}/tools/client_patch/build_aurora_login_ui_fix.py" \
  --aurora-dir "${PRIME_DIR}" \
  --patch-fr "${PRIME_DIR}/patch_fr_00.tre" \
  --aur-french "${PRIME_DIR}/LBG_French.tre" \
  --out "${TRE_FIX}"

cp -a "${CFG}" "${CFG}.bak_ui_fr"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out, seen99, seen98 = [], False, False
for line in lines:
    s = line.strip()
    if s.startswith("searchTree_00_99="):
        if not seen99:
            out.append("\tsearchTree_00_99=patch_prime_ui_fr_00.tre")
            seen99 = True
        continue
    if s.startswith("searchTree_00_98=") and "patch_fr" in s:
        if not seen98:
            out.append("\tsearchTree_00_98=patch_fr_00.tre")
            seen98 = True
        continue
    if s.startswith("searchTree_00_98=LBG_client"):
        if not seen98:
            out.append("\tsearchTree_00_98=patch_fr_00.tre")
            out.append("\tsearchTree_00_97=LBG_client.tre")
            seen98 = True
        continue
    out.append(line)
if not seen99:
    raise SystemExit("maxSearchPriority / searchTree_00_99 introuvable")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p)
PY

echo "OK — relancer lbgemu.exe (Prime). Skin Aurora = LBG_patch_026 (normal)."
