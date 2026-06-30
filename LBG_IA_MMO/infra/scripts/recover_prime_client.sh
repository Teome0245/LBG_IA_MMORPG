#!/usr/bin/env bash
# Rollback client Prime si lbgemu.exe quitte immédiatement (patch_lbg_00.tre corrompu).
#
# Usage :
#   bash infra/scripts/recover_prime_client.sh
#   PRIME_CLIENT=/mnt/j/swgemu/clients/prime-lbg bash infra/scripts/recover_prime_client.sh
#
set -euo pipefail

GAME_DIR="${PRIME_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
PRECU_DIR="${PRECU_CLIENT:-/mnt/j/swgemu/clients/precu-original}"

if [[ ! -d "${GAME_DIR}" ]]; then
  echo "ERROR: dossier Prime introuvable : ${GAME_DIR}" >&2
  exit 1
fi

echo ">> Désactivation patch_lbg_00.tre dans les .cfg"
for name in user.cfg swgemu_live.cfg; do
  path="${GAME_DIR}/${name}"
  [[ -f "${path}" ]] || continue
  cp -a "${path}" "${path}.bak_recover"
  python3 <<PY
from pathlib import Path
p = Path("${path}")
lines = []
for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if s.startswith("searchTree_00_99=patch_lbg_00.tre"):
        continue
    if s.startswith("searchTree_00_25=patch_lbg_00.tre"):
        continue
    if s.startswith("maxSearchPriority=99"):
        lines.append("\tmaxSearchPriority=98")
        continue
    lines.append(line)
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("  OK", p.name)
PY
done

tre="${GAME_DIR}/patch_lbg_00.tre"
if [[ -f "${tre}" ]]; then
  mv -f "${tre}" "${tre}.bak"
  echo ">> patch_lbg_00.tre → patch_lbg_00.tre.bak"
fi

precu="${PRECU_DIR}/SWGEmu.exe"
exe="${GAME_DIR}/lbgemu.exe"
if [[ -f "${precu}" && -f "${exe}" ]]; then
  cp -a "${exe}" "${exe}.bak_recover"
  cp -a "${precu}" "${exe}"
  echo ">> lbgemu.exe restauré depuis PreCu ($(stat -c%s "${exe}") octets)"
fi

echo ""
echo "OK — relancer le Launchpad Prime (rafraîchir statut serveur si besoin)."
echo "    Puis JOUER. Commande /lbgwe indisponible tant que patch_lbg est désactivé."
