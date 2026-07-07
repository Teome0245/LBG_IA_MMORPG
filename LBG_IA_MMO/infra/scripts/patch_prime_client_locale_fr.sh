#!/usr/bin/env bash
# FR Prime : LBG_French (23) + login inc corrigé (26).
# - defaultLocale=fr  (textes jeu)
# - fontLocale=en     (polices vanilla — fr casse le rendu login)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
VANILLA_REF="${VANILLA_REF:-/mnt/j/swgemu/StarWarsGalaxies}"
LOGIN_TRE="${PRIME_DIR}/patch_prime_fr_login_00.tre"
USER_CFG="${PRIME_DIR}/user.cfg"
OPTIONS_CFG="${PRIME_DIR}/options.cfg"
LIVE_CFG="${PRIME_DIR}/swgemu_live.cfg"

python3 "${ROOT_DIR}/tools/client_patch/build_prime_fr_login_fix.py" \
  --client-dir "${PRIME_DIR}" \
  --vanilla-ref "${VANILLA_REF}" \
  --out "${LOGIN_TRE}"

cp -a "${USER_CFG}" "${USER_CFG}.bak_fr_login"
[[ -f "${OPTIONS_CFG}" ]] && cp -a "${OPTIONS_CFG}" "${OPTIONS_CFG}.bak_fr_login"
[[ -f "${LIVE_CFG}" ]] && cp -a "${LIVE_CFG}" "${LIVE_CFG}.bak_fr_login"

cat > "${USER_CFG}" <<'EOF'
[SharedFile]
	searchTree_00_26=patch_prime_fr_login_00.tre
	searchTree_00_24=patch_fr_00.tre
	searchTree_00_23=LBG_French.tre

[SharedGame]
	defaultLocale=fr
	fontLocale=en

[ClientGame]
	skipSplash=1
EOF

if [[ -f "${OPTIONS_CFG}" ]]; then
  sed -i 's/defaultLocale=en/defaultLocale=fr/' "${OPTIONS_CFG}"
  sed -i 's/fontLocale=fr/fontLocale=en/' "${OPTIONS_CFG}"
  grep -q 'defaultLocale=fr' "${OPTIONS_CFG}" || {
    printf '\n[SharedGame]\n\tdefaultLocale=fr\n\tfontLocale=en\n' >> "${OPTIONS_CFG}"
  }
fi

sed -i 's/maxSearchPriority=25/maxSearchPriority=26/' "${LIVE_CFG}"
sed -i 's/maxSearchPriority=99/maxSearchPriority=26/' "${LIVE_CFG}"
grep -q 'maxSearchPriority=26' "${LIVE_CFG}" || \
  sed -i 's/maxSearchPriority=[0-9]*/maxSearchPriority=26/' "${LIVE_CFG}"

rm -f "${PRIME_DIR}"/misc/cache*.iff 2>/dev/null || true

# Anciens patchs expérimentaux hors service
for f in patch_prime_fr_stf_00.tre patch_prime_login_fix_00.tre; do
  [[ -f "${PRIME_DIR}/${f}" ]] && mv -f "${PRIME_DIR}/${f}" "${PRIME_DIR}/${f}.off_fr_login"
done

echo ""
echo "OK — FR Prime (login corrigé)."
echo "  26 : patch_prime_fr_login_00.tre  ([@username] + GetsInput)"
echo "  24 : patch_fr_00.tre"
echo "  23 : LBG_French.tre"
echo "  locale=fr  fontLocale=en (polices vanilla)"
