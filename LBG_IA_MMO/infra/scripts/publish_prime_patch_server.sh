#!/usr/bin/env bash
# Publie le manifest Prime (canal Launchpad).
#
# Modes (un seul à la fois) :
#   PRIME_PATCH_VANILLA=1  — reset aligné PreCu (en)
#   PRIME_PATCH_FR=1       — étape 1 : locale FR + LBG_French.tre
#   défaut                 — pipeline branding LBG (expérimental)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_CLIENT="${PRIME_LBG_CLIENT:-/mnt/j/swgemu/clients/prime-lbg}"
PATCH_SRC="${ROOT_DIR}/infra/client-patch-server/patches/prime"
PATCH_HOST="${PATCH_SERVER_HOST:-192.168.0.245}"
PATCH_USER="${PATCH_SERVER_USER:-lbg}"
PATCH_REMOTE="${PATCH_REMOTE_DIR:-/home/lbg/lbg-client-patches/patches/prime}"

if [[ "${PRIME_PATCH_VANILLA:-0}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/align_prime_client_precu.sh"
elif [[ "${PRIME_PATCH_FR:-0}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/patch_prime_client_locale_fr.sh"
  bash "${ROOT_DIR}/infra/scripts/patch_prime_client_lbg_content.sh"
else
  bash "${ROOT_DIR}/infra/scripts/patch_prime_login_background.sh"
fi

mkdir -p "${PATCH_SRC}"

CFG_FILES="swgemu_live.cfg swgemu_login.cfg swgemu.cfg swgemu_preload.cfg user.cfg options.cfg"
for f in ${CFG_FILES}; do
  cp -f "${PRIME_CLIENT}/${f}" "${PATCH_SRC}/"
done

rm -f "${PATCH_SRC}/patch_lbg_00.tre" "${PATCH_SRC}/patch_lbg_01.tre"
rm -f "${PATCH_SRC}/patch_prime_fr_stf_00.tre" "${PATCH_SRC}/patch_prime_fr_login_00.tre"

TRE_FILES=""
if [[ "${PRIME_PATCH_FR:-0}" == "1" ]]; then
  if [[ -f "${PRIME_CLIENT}/patch_prime_fr_login_00.tre" ]]; then
    cp -f "${PRIME_CLIENT}/patch_prime_fr_login_00.tre" "${PATCH_SRC}/"
    TRE_FILES=" patch_prime_fr_login_00.tre"
  fi
elif [[ "${PRIME_PATCH_VANILLA:-0}" != "1" ]]; then
  for f in patch_prime_login_00.tre patch_prime_ui_fr_00.tre; do
    if [[ -f "${PRIME_CLIENT}/${f}" ]]; then
      cp -f "${PRIME_CLIENT}/${f}" "${PATCH_SRC}/"
      TRE_FILES="${TRE_FILES} ${f}"
    fi
  done
fi

if [[ "${PRIME_PATCH_VANILLA:-0}" == "1" ]]; then
  MANIFEST_VERSION="prime-precu-$(date +%Y%m%d)"
elif [[ "${PRIME_PATCH_FR:-0}" == "1" ]]; then
  MANIFEST_VERSION="prime-fr-step1-$(date +%Y%m%d)"
else
  MANIFEST_VERSION="prime-20260630"
fi

export PATCH_SRC PRIME_CLIENT MANIFEST_VERSION CFG_FILES TRE_FILES
python3 <<'PY'
import hashlib, json, os
from pathlib import Path

src = Path(os.environ["PATCH_SRC"])
client = Path(os.environ["PRIME_CLIENT"])
cfg_files = os.environ["CFG_FILES"].split()
tre_files = [f for f in os.environ.get("TRE_FILES", "").split() if f]
files = ["lbgemu.exe", *cfg_files, *tre_files]
manifest = {"version": os.environ["MANIFEST_VERSION"], "files": []}
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
if [[ "${PRIME_PATCH_VANILLA:-0}" == "1" ]]; then
  echo "Canal Prime = copie config PreCu + login 246 (sans TRE custom)."
elif [[ "${PRIME_PATCH_FR:-0}" == "1" ]]; then
  echo "Canal Prime = PreCu + locale FR (LBG_French.tre prio 25)."
else
  echo "Canal Prime = branding LBG (expérimental)."
fi
