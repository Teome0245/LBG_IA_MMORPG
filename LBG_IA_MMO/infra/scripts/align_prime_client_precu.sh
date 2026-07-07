#!/usr/bin/env bash
# Aligne le client Prime sur la config PreCu qui fonctionne (StarWarsGalaxies).
# Seule différence volontaire : swgemu_login.cfg → serveur Prime 246.
#
# Cause identifiée : locale=fr sans string/fr/ui.stf dans les TRE vanilla → login cassé.
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRECU_DIR="${PRECU_CLIENT:-/mnt/j/swgemu/StarWarsGalaxies}"
PRIME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
PRIME_LOGIN_HOST="${PRIME_LOGIN_HOST:-192.168.0.246}"
PRIME_LOGIN_PORT="${PRIME_LOGIN_PORT:-44553}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${PRIME_DIR}/_backup_precu_align_${STAMP}"

for d in "${PRECU_DIR}" "${PRIME_DIR}"; do
  [[ -d "${d}" ]] || { echo "ERROR: absent ${d}" >&2; exit 1; }
done

mkdir -p "${BACKUP_DIR}"
for f in user.cfg options.cfg swgemu.cfg swgemu_live.cfg swgemu_login.cfg; do
  [[ -f "${PRIME_DIR}/${f}" ]] && cp -a "${PRIME_DIR}/${f}" "${BACKUP_DIR}/"
done

# Config identique PreCu (testé OK par l'utilisateur).
cp -a "${PRECU_DIR}/user.cfg" "${PRIME_DIR}/user.cfg"
cp -a "${PRECU_DIR}/options.cfg" "${PRIME_DIR}/options.cfg"
cp -a "${PRECU_DIR}/swgemu_live.cfg" "${PRIME_DIR}/swgemu_live.cfg"
cp -a "${PRECU_DIR}/swgemu.cfg" "${PRIME_DIR}/swgemu.cfg"

cat > "${PRIME_DIR}/swgemu_login.cfg" <<EOF
[ClientGame]
loginServerAddress0=${PRIME_LOGIN_HOST}
loginServerPort0=${PRIME_LOGIN_PORT}
EOF

# Retirer correctifs login expérimentaux (non nécessaires si cfg = PreCu).
for f in patch_prime_login_fix_00.tre patch_prime_login_00.tre patch_prime_ui_fr_00.tre; do
  [[ -f "${PRIME_DIR}/${f}" ]] && mv -f "${PRIME_DIR}/${f}" "${PRIME_DIR}/${f}.off_precu_align"
done

# Cache UI client (peut garder un état corrompu entre tentatives).
rm -f "${PRIME_DIR}"/misc/cache*.iff 2>/dev/null || true

if [[ -f "${PRECU_DIR}/SWGEmu.exe" ]]; then
  cp -a "${PRECU_DIR}/SWGEmu.exe" "${PRIME_DIR}/lbgemu.exe"
fi

echo ""
echo "OK — Prime aligné sur PreCu (StarWarsGalaxies)."
echo "  locale       : en (comme PreCu — FR à réactiver plus tard)"
echo "  login        : ${PRIME_LOGIN_HOST}:${PRIME_LOGIN_PORT}"
echo "  sauvegarde   : ${BACKUP_DIR}"
echo ""
echo "Relancer Launchpad → Vérifier mises à jour → lbgemu.exe"
