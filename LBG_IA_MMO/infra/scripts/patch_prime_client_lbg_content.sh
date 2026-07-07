#!/usr/bin/env bash
# Étape 3 : assets LBG (monde Prime) + login FR en prio 99.
# Sans les TRE LBG (prio 30–97), le client bloque sur « Chargement des objets… ».
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
LIVE_SRC="${PRIME_DIR}/swgemu_live.cfg.bak_login_lbg"
LIVE_CFG="${PRIME_DIR}/swgemu_live.cfg"
USER_CFG="${PRIME_DIR}/user.cfg"
LOGIN_TRE="${PRIME_DIR}/patch_prime_fr_login_00.tre"

if [[ ! -f "${LIVE_SRC}" ]]; then
  echo "ERROR: ${LIVE_SRC} introuvable — restaurer une sauvegarde LBG" >&2
  exit 1
fi

# S'assurer que le TRE login FR existe
if [[ ! -f "${LOGIN_TRE}" ]]; then
  python3 "${ROOT_DIR}/tools/client_patch/build_prime_fr_login_fix.py" \
    --client-dir "${PRIME_DIR}" \
    --out "${LOGIN_TRE}"
fi

cp -a "${LIVE_CFG}" "${LIVE_CFG}.bak_before_lbg_content"
cp -a "${LIVE_SRC}" "${LIVE_CFG}"

python3 <<PY
from pathlib import Path
p = Path("${LIVE_CFG}")
skip_substrings = (
    "patch_prime_login_00", "patch_prime_ui_fr", "patch_lbg_",
    "LBG_future_add.tre", "LBG_patch_026.tre",
)
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
for line in lines:
    s = line.strip()
    if any(x in s for x in skip_substrings):
        continue
    out.append(line)
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Patched:", p, "(LBG complet sauf future_add + Aurora 026; carte vanilla en prio 99)")
PY

python3 "${ROOT_DIR}/tools/client_patch/build_prime_fr_login_fix.py" \
  --client-dir "${PRIME_DIR}" \
  --vanilla-ref "${VANILLA_REF:-/mnt/j/swgemu/StarWarsGalaxies}" \
  --out "${LOGIN_TRE}"

cat > "${USER_CFG}" <<'EOF'
[SharedFile]
	searchTree_00_99=patch_prime_fr_login_00.tre

[SharedGame]
	defaultLocale=fr
	fontLocale=en

[ClientGame]
	skipSplash=1
EOF

rm -f "${PRIME_DIR}"/misc/cache*.iff 2>/dev/null || true

echo ""
echo "OK — contenu LBG (LBG_planets OK, carte vanilla prio 99)."
echo "  Exclus : LBG_future_add, LBG_patch_026 (Aurora)"
echo ""
echo "Attendre ~2 min après un restart Prime avant de jouer (boot zone)."
