#!/usr/bin/env bash
# Vérifie / prépare Teome sur Prime (246) + cfg client prime-lbg.
#
# Usage :
#   bash infra/scripts/ensure_teome_prime_account.sh
#   TEOME_PASSWORD='secret' bash infra/scripts/ensure_teome_prime_account.sh --create-if-missing
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_HOST="${LBG_PRIME_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
PRIME_CLIENT="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
TEOME_USER="${TEOME_USERNAME:-Teome}"
TEOME_PASS="${TEOME_PASSWORD:-}"
CREATE=0

for arg in "$@"; do
  case "$arg" in
    --create-if-missing) CREATE=1 ;;
  esac
done

echo "=== Prime ${PRIME_HOST} — compte ${TEOME_USER} ==="

ACC_LINE="$(ssh "${VM_USER}@${PRIME_HOST}" "sudo mysql -N swgemu -e \
  \"SELECT account_id, username, admin_level FROM accounts WHERE LOWER(username)=LOWER('${TEOME_USER}') LIMIT 1;\"" 2>/dev/null || true)"

if [[ -z "${ACC_LINE}" ]]; then
  echo "Compte ${TEOME_USER} : ABSENT sur DB Prime"
  if [[ "${CREATE}" != "1" || -z "${TEOME_PASS}" ]]; then
    echo "  Créer via UI http://${PRIME_HOST}:8792/ ou :" >&2
    echo "  TEOME_PASSWORD='...' bash infra/scripts/ensure_teome_prime_account.sh --create-if-missing" >&2
    exit 1
  fi
  echo "Création compte (admin_level=2 Mod+)…"
  ssh "${VM_USER}@${PRIME_HOST}" "bash -s" <<EOF
set -euo pipefail
HASH=\$(cd /opt/lbg-new-mmo-clean/MMOCoreORB/bin 2>/dev/null && ./core3client hashpassword '${TEOME_PASS}' 2>/dev/null || echo '')
if [[ -z "\${HASH}" ]]; then
  echo "WARN: hashpassword indisponible — créer le compte via UI 8792" >&2
  exit 1
fi
sudo mysql swgemu -e "INSERT INTO accounts (username, password, admin_level, active) VALUES ('${TEOME_USER}', '\${HASH}', 2, 1);"
EOF
  ACC_LINE="$(ssh "${VM_USER}@${PRIME_HOST}" "sudo mysql -N swgemu -e \
    \"SELECT account_id, username, admin_level FROM accounts WHERE LOWER(username)=LOWER('${TEOME_USER}') LIMIT 1;\"")"
fi

echo "Compte SQL : ${ACC_LINE}"

CHAR_LINE="$(ssh "${VM_USER}@${PRIME_HOST}" "sudo mysql -N swgemu -e \
  \"SELECT c.character_id, c.firstname, c.account_id FROM characters c \
   JOIN accounts a ON a.account_id=c.account_id \
   WHERE LOWER(a.username)=LOWER('${TEOME_USER}') LIMIT 5;\"" 2>/dev/null || true)"
if [[ -n "${CHAR_LINE}" ]]; then
  echo "Personnages :"
  echo "${CHAR_LINE}" | while read -r row; do echo "  ${row}"; done
else
  echo "Aucun personnage — créer un perso en jeu après login."
fi

if [[ -d "${PRIME_CLIENT}" ]]; then
  LOGIN_CFG="${PRIME_CLIENT}/swgemu_login.cfg"
  if [[ -f "${LOGIN_CFG}" ]]; then
    cp -a "${LOGIN_CFG}" "${LOGIN_CFG}.bak_teome" 2>/dev/null || true
    python3 <<PY
from pathlib import Path
p = Path("${LOGIN_CFG}")
text = p.read_text(encoding="utf-8", errors="replace")
lines = []
for line in text.splitlines():
    if line.startswith("loginServerAddress0="):
        lines.append("loginServerAddress0=${PRIME_HOST}")
    elif line.startswith("loginServerPort0="):
        lines.append("loginServerPort0=44553")
    else:
        lines.append(line)
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Client Prime cfg:", p)
PY
  fi
fi

echo ""
echo "Client Prime : ${PRIME_CLIENT}"
echo "  Login → ${PRIME_HOST}:44553 (galaxie 3)"
echo "  Profil Launchpad : prime (pas Aurora / swg-aurora.fr)"
