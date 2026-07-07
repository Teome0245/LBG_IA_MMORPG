#!/usr/bin/env bash
# Restaure assets LBG_patch_026 + login 029 via patch_prime (priorité 99).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
TRASH="/mnt/j/swgemu/_trash_patch_lbg_20260630/LBG_patch_026.tre"
CFG="${PRIME_DIR}/swgemu_live.cfg"

if [[ -f "${TRASH}" && ! -f "${PRIME_DIR}/LBG_patch_026.tre" ]]; then
  cp -f "${TRASH}" "${PRIME_DIR}/LBG_patch_026.tre"
  echo "Restauré LBG_patch_026.tre (fond Aurora) — login UI = 029 via patch_prime"
fi

export PRIME_LOGIN_RAW=0
bash "${ROOT_DIR}/infra/scripts/patch_prime_login_background.sh"

python3 <<PY
from pathlib import Path
p = Path("${CFG}")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out, seen55 = [], False
for line in lines:
    s = line.strip()
    if s.startswith("# searchTree_00_55=LBG_patch_026.tre"):
        out.append("\tsearchTree_00_55=LBG_patch_026.tre")
        seen55 = True
        continue
    if s == "searchTree_00_55=LBG_patch_026.tre":
        seen55 = True
    out.append(line)
if not seen55:
    for i, line in enumerate(out):
        if "searchTree_00_56=LBG_patch_027.tre" in line:
            out.insert(i, "\tsearchTree_00_55=LBG_patch_026.tre")
            break
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Réactivé searchTree_00_55=LBG_patch_026.tre (assets)")
PY

bash "${ROOT_DIR}/infra/scripts/publish_prime_patch_server.sh"
