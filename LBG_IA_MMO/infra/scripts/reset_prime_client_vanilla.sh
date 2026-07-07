#!/usr/bin/env bash
# Remet le client Prime sur la base vanilla (StarWarsGalaxies) : login PreCu connu,
# sans TRE LBG ni patch_prime_login. Seul changement réseau : serveur Prime 246.
#
# Usage :
#   bash infra/scripts/reset_prime_client_vanilla.sh
#   VANILLA_REF=/mnt/j/swgemu/StarWarsGalaxies PRIME_CLIENT=/mnt/j/swgemu/clients/prime-lbg bash ...
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VANILLA_REF="${VANILLA_REF:-/mnt/j/swgemu/StarWarsGalaxies}"
PRIME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
PRIME_LOGIN_HOST="${PRIME_LOGIN_HOST:-192.168.0.246}"
PRIME_LOGIN_PORT="${PRIME_LOGIN_PORT:-44553}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${PRIME_DIR}/_backup_vanilla_${STAMP}"

for d in "${VANILLA_REF}" "${PRIME_DIR}"; do
  if [[ ! -d "${d}" ]]; then
    echo "ERROR: dossier absent : ${d}" >&2
    exit 1
  fi
done

mkdir -p "${BACKUP_DIR}"
for f in swgemu_live.cfg swgemu_login.cfg user.cfg swgemu.cfg options.cfg lbgemu_client.cfg manifest.json; do
  [[ -f "${PRIME_DIR}/${f}" ]] && cp -a "${PRIME_DIR}/${f}" "${BACKUP_DIR}/"
done
for f in patch_prime_login_00.tre patch_prime_ui_fr_00.tre; do
  [[ -f "${PRIME_DIR}/${f}" ]] && mv -f "${PRIME_DIR}/${f}" "${PRIME_DIR}/${f}.off_vanilla"
done

# Binaire identique à PreCu (même hash MD5) — on s'aligne sur la référence.
if [[ -f "${VANILLA_REF}/SWGEmu.exe" ]]; then
  cp -a "${VANILLA_REF}/SWGEmu.exe" "${PRIME_DIR}/lbgemu.exe"
fi

# swgemu_live.cfg : copie exacte de la référence vanilla (patch_00…patch_fr, prio 25).
cp -a "${VANILLA_REF}/swgemu_live.cfg" "${PRIME_DIR}/swgemu_live.cfg"

# swgemu_login.cfg : uniquement l'adresse Prime.
cat > "${PRIME_DIR}/swgemu_login.cfg" <<EOF
[ClientGame]
loginServerAddress0=${PRIME_LOGIN_HOST}
loginServerPort0=${PRIME_LOGIN_PORT}
EOF

# user.cfg : FR + skip splash (confort), pas de TRE custom hors patch_fr.
cat > "${PRIME_DIR}/user.cfg" <<'EOF'
[SharedFile]
	searchTree_00_24=patch_fr_00.tre

[SharedGame]
	defaultLocale=fr
	fontLocale=fr

[ClientGame]
	skipSplash=1
	skipIntro=1
	splashTimeoutSeconds=0
	disableCutScenes=1
EOF

# swgemu.cfg : chaîne minimale (sans lbgemu_client.cfg optionnel).
cat > "${PRIME_DIR}/swgemu.cfg" <<'EOF'
.include "swgemu_login.cfg"
.include "swgemu_live.cfg"
.include "swgemu_preload.cfg"
.include "options.cfg"
.include "user.cfg"
EOF

# options FR
if [[ -f "${PRIME_DIR}/options.cfg" ]]; then
  sed -i 's/defaultLocale=en/defaultLocale=fr/' "${PRIME_DIR}/options.cfg"
  sed -i 's/fontLocale=en/fontLocale=fr/' "${PRIME_DIR}/options.cfg"
fi

# Archiver les anciens patch_lbg s'ils traînent encore dans le dossier.
TRASH_DIR="/mnt/j/swgemu/_trash_patch_lbg_${STAMP}"
mkdir -p "${TRASH_DIR}"
for f in patch_lbg_00.tre patch_lbg_01.tre; do
  [[ -f "${PRIME_DIR}/${f}" ]] && mv -f "${PRIME_DIR}/${f}" "${TRASH_DIR}/"
done

echo ""
echo "OK — client Prime remis en mode vanilla."
echo "  Référence     : ${VANILLA_REF}"
echo "  Client Prime  : ${PRIME_DIR}"
echo "  Login         : ${PRIME_LOGIN_HOST}:${PRIME_LOGIN_PORT}"
echo "  Sauvegarde    : ${BACKUP_DIR}"
echo ""
echo "Aucun LBG_patch_* ni patch_prime_* chargé."
echo "Pour aligner sur PreCu (recommandé) : bash infra/scripts/align_prime_client_precu.sh"
echo "Relancer Launchpad → Vérifier mises à jour → JOUER (profil Prime)."
