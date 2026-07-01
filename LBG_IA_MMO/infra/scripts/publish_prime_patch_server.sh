#!/usr/bin/env bash
# Publie le manifest Prime sur le serveur de patch (Launchpad → :8080).
# Sans ça, « Vérifier mises à jour » réinjecte patch_lbg_01 + login Aurora cassé.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_CLIENT="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
PATCH_SRC="${ROOT_DIR}/infra/client-patch-server/patches/prime"
PATCH_HOST="${PATCH_SERVER_HOST:-192.168.0.245}"
PATCH_USER="${PATCH_SERVER_USER:-lbg}"
PATCH_REMOTE="${PATCH_REMOTE_DIR:-/home/lbg/lbg-client-patches/patches/prime}"

bash "${ROOT_DIR}/infra/scripts/patch_prime_login_background.sh"

mkdir -p "${PATCH_SRC}"

for f in swgemu_live.cfg swgemu_login.cfg swgemu.cfg swgemu_preload.cfg user.cfg lbgemu_client.cfg options.cfg; do
  cp -f "${PRIME_CLIENT}/${f}" "${PATCH_SRC}/${f}"
done
cp -f "${PRIME_CLIENT}/patch_prime_login_00.tre" "${PATCH_SRC}/"
cp -f "${PRIME_CLIENT}/patch_prime_ui_fr_00.tre" "${PATCH_SRC}/"

# Retirer anciens TRE cassés du dépôt patch
rm -f "${PATCH_SRC}/patch_lbg_00.tre" "${PATCH_SRC}/patch_lbg_01.tre"

python3 <<PY
import hashlib, json
from pathlib import Path
src = Path("${PATCH_SRC}")
files = [
    "lbgemu.exe",
    "swgemu.cfg",
    "swgemu_login.cfg",
    "swgemu_live.cfg",
    "swgemu_preload.cfg",
    "user.cfg",
    "lbgemu_client.cfg",
    "options.cfg",
    "patch_prime_login_00.tre",
    "patch_prime_ui_fr_00.tre",
]
client = Path("${PRIME_CLIENT}")
manifest = {"version": "prime-20260630", "files": []}
for name in files:
    p = client / name if name == "lbgemu.exe" else src / name
    if not p.is_file():
        print("SKIP (absent):", name)
        continue
    h = hashlib.md5(p.read_bytes()).hexdigest()
    manifest["files"].append({"name": name, "hash": h})
    print(f"  {name}  {h}")
(src / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("OK manifest:", src / "manifest.json")
PY

cp -f "${PATCH_SRC}/manifest.json" "${PRIME_CLIENT}/manifest.json"

if ssh -o ConnectTimeout=3 "${PATCH_USER}@${PATCH_HOST}" "test -d '${PATCH_REMOTE}'" 2>/dev/null; then
  echo "Sync → ${PATCH_USER}@${PATCH_HOST}:${PATCH_REMOTE}"
  scp -q "${PATCH_SRC}/"* "${PATCH_USER}@${PATCH_HOST}:${PATCH_REMOTE}/"
  echo "Serveur de patch mis à jour."
else
  echo "AVERT: SSH ${PATCH_HOST} indisponible — fichiers prêts dans ${PATCH_SRC}"
fi

echo ""
echo "Terminé. Ne pas utiliser l'ancien patch_lbg_01 sur le client."
