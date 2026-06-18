#!/usr/bin/env bash
set -euo pipefail

# Déploie l'UI Companion (Vite build) dans pilot_web/compagnon/ sur la VM front (110).
#
# Par défaut :
# - build local dans `companion_bot/web` avec `--base=/compagnon/`
# - validation dist/index.html -> dist/assets/*
# - rsync atomique vers /opt/LBG_IA_MMO/pilot_web/compagnon + backup
#
# Variables :
#   LBG_VM_HOST                    défaut: 192.168.0.110
#   LBG_VM_USER                    défaut: lbg
#   LBG_COMPANION_WEB_KEEP_RELEASES défaut: 5
#   LBG_COMPANION_WEB_DEPLOY_LOCAL_ONLY=1 : copie uniquement dans le repo (pilot_web/compagnon), sans SSH
#
# Exemple (local-only) :
#   cd LBG_IA_MMO && LBG_COMPANION_WEB_DEPLOY_LOCAL_ONLY=1 bash infra/scripts/deploy_companion_web.sh

VM_HOST="${LBG_VM_HOST:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
REMOTE_DIR="/opt/LBG_IA_MMO/pilot_web/compagnon"
REMOTE_RELEASES_DIR="/opt/LBG_IA_MMO/pilot_web/compagnon_releases"
KEEP_RELEASES="${LBG_COMPANION_WEB_KEEP_RELEASES:-5}"
LOCAL_ONLY="${LBG_COMPANION_WEB_DEPLOY_LOCAL_ONLY:-0}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_DIR="${ROOT_DIR}/companion_bot/web"

sync_local_pilot_companion() {
  local LOCAL_TARGET="${ROOT_DIR}/pilot_web/compagnon"
  local LOCAL_STAGE="${ROOT_DIR}/pilot_web/.compagnon_stage"
  local LOCAL_BACKUP="${ROOT_DIR}/pilot_web/.compagnon_backup"

  mkdir -p "${LOCAL_STAGE}"
  rsync -a --delete "${WEB_DIR}/dist/" "${LOCAL_STAGE}/"
  if [[ -d "${LOCAL_TARGET}" ]]; then
    rm -rf "${LOCAL_BACKUP}" || true
    cp -a "${LOCAL_TARGET}" "${LOCAL_BACKUP}" || true
  fi
  rm -rf "${LOCAL_TARGET}" || true
  mv "${LOCAL_STAGE}" "${LOCAL_TARGET}"
}

echo "Compiling companion UI with base /compagnon/..."
cd "${WEB_DIR}"
npm run build -- --base=/compagnon/

echo "Vérification du build (index.html → assets)…"
INDEX_HTML="${WEB_DIR}/dist/index.html"
if [[ ! -f "${INDEX_HTML}" ]]; then
  echo "ERREUR: dist/index.html introuvable après build" >&2
  exit 1
fi

mapfile -t REF_ASSETS < <(python3 - <<'PY'
import re, pathlib
p = pathlib.Path("dist/index.html")
txt = p.read_text(encoding="utf-8", errors="replace")
refs = set()
for m in re.finditer(r'''(?:src|href)=["']([^"']+)["']''', txt):
    u = m.group(1)
    if "/assets/" in u:
        refs.add(u.split("/assets/", 1)[1])
    elif u.startswith("assets/"):
        refs.add(u.split("assets/", 1)[1])
for r in sorted(refs):
    print(r)
PY
)

missing=0
for a in "${REF_ASSETS[@]}"; do
  if [[ ! -f "${WEB_DIR}/dist/assets/${a}" ]]; then
    echo "ERREUR: asset référencé manquant: dist/assets/${a}" >&2
    missing=1
  fi
done
if [[ "${missing}" -ne 0 ]]; then
  echo "Build invalide: index.html référence des assets absents. Déploiement annulé." >&2
  exit 1
fi

echo "Synchronisation locale vers pilot_web/compagnon/…"
sync_local_pilot_companion
echo "OK : ${ROOT_DIR}/pilot_web/compagnon"

if [[ "${LOCAL_ONLY}" == "1" ]]; then
  echo "LBG_COMPANION_WEB_DEPLOY_LOCAL_ONLY=1 → arrêt ici (pas de SSH)."
  exit 0
fi

echo "Déploiement vers ${VM_USER}@${VM_HOST}:${REMOTE_DIR}..."

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "
  sudo mkdir -p ${REMOTE_DIR} ${REMOTE_RELEASES_DIR}
  sudo chown -R ${VM_USER}:${VM_USER} ${REMOTE_DIR} ${REMOTE_RELEASES_DIR}
"

REL_ID="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="${REMOTE_RELEASES_DIR}/stage_${REL_ID}"
REMOTE_BACKUP="${REMOTE_RELEASES_DIR}/backup_${REL_ID}"

echo "Rsync vers stage: ${REMOTE_STAGE}…"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "rm -rf '${REMOTE_STAGE}' && mkdir -p '${REMOTE_STAGE}'"
rsync -a --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  "${WEB_DIR}/dist/" \
  "${VM_USER}@${VM_HOST}:${REMOTE_STAGE}/"

echo "Validation distante (index.html -> assets)…"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "python3 - <<'PY'
import re, pathlib, sys
root = pathlib.Path('${REMOTE_STAGE}')
idx = root / 'index.html'
if not idx.exists():
    print('missing index.html', file=sys.stderr)
    raise SystemExit(1)
txt = idx.read_text(encoding='utf-8', errors='replace')
refs = set()
for m in re.finditer(r'(?:src|href)=[\"\\']([^\"\\']+)[\"\\']', txt):
    u = m.group(1)
    if '/assets/' in u:
        refs.add(u.split('/assets/', 1)[1])
    elif u.startswith('assets/'):
        refs.add(u.split('assets/', 1)[1])
missing = [r for r in sorted(refs) if not (root / 'assets' / r).exists()]
if missing:
    print('missing assets:', missing, file=sys.stderr)
    raise SystemExit(2)
print('ok')
PY"

echo "Backup + switch atomique…"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "set -eu
  if [ -d '${REMOTE_DIR}' ] && [ -f '${REMOTE_DIR}/index.html' ]; then
    rm -rf '${REMOTE_BACKUP}' || true
    cp -a '${REMOTE_DIR}' '${REMOTE_BACKUP}'
  fi
  rm -rf '${REMOTE_DIR}'
  mv '${REMOTE_STAGE}' '${REMOTE_DIR}'
  ls -1dt '${REMOTE_RELEASES_DIR}'/backup_* 2>/dev/null | tail -n +$(( ${KEEP_RELEASES} + 1 )) | xargs -r rm -rf
  ls -1dt '${REMOTE_RELEASES_DIR}'/stage_* 2>/dev/null | tail -n +$(( ${KEEP_RELEASES} + 1 )) | xargs -r rm -rf
"

echo "Restart nginx…"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "sudo systemctl restart nginx"

echo "Companion UI déployée : http://${VM_HOST}:8080/compagnon/ (ou :80 selon nginx)"

