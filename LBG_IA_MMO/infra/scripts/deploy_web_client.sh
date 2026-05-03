#!/usr/bin/env bash
set -euo pipefail

VM_HOST="${LBG_VM_HOST:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
# On déploie maintenant dans un sous-dossier de pilot_web pour Nginx
REMOTE_DIR="/opt/LBG_IA_MMO/pilot_web/mmo"
REMOTE_RELEASES_DIR="/opt/LBG_IA_MMO/pilot_web/mmo_releases"
KEEP_RELEASES="${LBG_MMO_WEB_KEEP_RELEASES:-5}"
# 1 : build + vérifications + copie vers LBG_IA_MMO/pilot_web/mmo uniquement (pas de SSH VM).
LBG_MMO_WEB_DEPLOY_LOCAL_ONLY="${LBG_MMO_WEB_DEPLOY_LOCAL_ONLY:-0}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/../web_client"

sync_local_pilot_mmo() {
  local LOCAL_TARGET="${ROOT_DIR}/pilot_web/mmo"
  local LOCAL_STAGE="${ROOT_DIR}/pilot_web/.mmo_stage"
  local LOCAL_BACKUP="${ROOT_DIR}/pilot_web/.mmo_backup"

  mkdir -p "${LOCAL_STAGE}"
  rsync -a --delete "${CLIENT_DIR}/dist/" "${LOCAL_STAGE}/"
  if [[ -d "${LOCAL_TARGET}" ]]; then
    rm -rf "${LOCAL_BACKUP}" || true
    cp -a "${LOCAL_TARGET}" "${LOCAL_BACKUP}" || true
  fi
  rm -rf "${LOCAL_TARGET}" || true
  mv "${LOCAL_STAGE}" "${LOCAL_TARGET}"
}

echo "Compiling client with base /mmo/..."
cd "${CLIENT_DIR}"
npm run build -- --base=/mmo/

echo "Vérification du build (index.html → assets)…"
INDEX_HTML="${CLIENT_DIR}/dist/index.html"
if [[ ! -f "${INDEX_HTML}" ]]; then
  echo "ERREUR: dist/index.html introuvable après build" >&2
  exit 1
fi

# Extraire les assets référencés par index.html (JS/CSS) et vérifier qu'ils existent.
# On supporte href/src sous /mmo/assets/… ou assets/…
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
  if [[ ! -f "${CLIENT_DIR}/dist/assets/${a}" ]]; then
    echo "ERREUR: asset référencé manquant: dist/assets/${a}" >&2
    missing=1
  fi
done
if [[ "${missing}" -ne 0 ]]; then
  echo "Build invalide: index.html référence des assets absents. Déploiement annulé." >&2
  exit 1
fi

echo "Vérification anti-régression du bundle MMO…"
python3 - <<'PY'
from pathlib import Path
import re

idx = Path("dist/index.html").read_text(encoding="utf-8", errors="replace")
match = re.search(r'''src=["'](?:/mmo/)?assets/([^"']+\.js)["']''', idx)
if not match:
    raise SystemExit("ERREUR: bundle JS introuvable dans dist/index.html")
bundle = Path("dist/assets") / match.group(1)
text = bundle.read_text(encoding="utf-8", errors="replace")
required = [
    "cameraX",
    "screenToWorld",
    "drawWorldMap",
    "drawVillageMap",
    "bourg_palette_map",
]
missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit(f"ERREUR: bundle MMO sans marqueurs top-down stables: {missing}")
if "x / 2 - y / 2" in text:
    raise SystemExit("ERREUR: bundle MMO contient l'ancien rendu isométrique régressif")
print(f"ok ({bundle.name})")
PY

if [[ "${LBG_MMO_WEB_DEPLOY_LOCAL_ONLY}" == "1" ]]; then
  echo "LBG_MMO_WEB_DEPLOY_LOCAL_ONLY=1 → synchronisation locale vers pilot_web/mmo uniquement."
  sync_local_pilot_mmo
  echo "OK : ${ROOT_DIR}/pilot_web/mmo"
  exit 0
fi

echo "Déploiement du client MMO vers ${VM_USER}@${VM_HOST}:${REMOTE_DIR}..."

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

# 1. Préparation du dossier et nettoyage de l'ancien service 8081
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "
  sudo systemctl stop lbg-web-client.service 2>/dev/null || true
  sudo systemctl disable lbg-web-client.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/lbg-web-client.service
  sudo systemctl daemon-reload
  sudo mkdir -p ${REMOTE_DIR} ${REMOTE_RELEASES_DIR}
  sudo chown -R ${VM_USER}:${VM_USER} ${REMOTE_DIR} ${REMOTE_RELEASES_DIR}
"

# 2. Déploiement atomique avec backup (évite les régressions "massives")
REL_ID="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="${REMOTE_RELEASES_DIR}/stage_${REL_ID}"
REMOTE_BACKUP="${REMOTE_RELEASES_DIR}/backup_${REL_ID}"

echo "Rsync vers stage: ${REMOTE_STAGE}…"
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "rm -rf '${REMOTE_STAGE}' && mkdir -p '${REMOTE_STAGE}'"
rsync -a --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  "${CLIENT_DIR}/dist/" \
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
  # Nettoyage des vieux backups/releases (on garde KEEP_RELEASES)
  ls -1dt '${REMOTE_RELEASES_DIR}'/backup_* 2>/dev/null | tail -n +$(( ${KEEP_RELEASES} + 1 )) | xargs -r rm -rf
  ls -1dt '${REMOTE_RELEASES_DIR}'/stage_* 2>/dev/null | tail -n +$(( ${KEEP_RELEASES} + 1 )) | xargs -r rm -rf
"

# 3. Redémarrage de Nginx pour prise en compte (optionnel mais recommandé)
ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "sudo systemctl restart nginx"

# 4. Sync locale (pour visibilité dans l'explorateur)
echo "Synchronisation locale vers LBG_IA_MMO/pilot_web/mmo/..."
sync_local_pilot_mmo

echo "Client MMO déployé et accessible sur http://192.168.0.110:8080/mmo/"
echo "L'interface Lyra reste sur http://${VM_HOST}:8080/"
