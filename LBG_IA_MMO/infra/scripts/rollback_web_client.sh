#!/usr/bin/env bash
set -euo pipefail

VM_HOST="${LBG_VM_HOST:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
REMOTE_ROOT="/opt/LBG_IA_MMO/pilot_web"
REMOTE_DIR="${REMOTE_ROOT}/mmo"
REMOTE_RELEASES_DIR="${REMOTE_ROOT}/mmo_releases"

SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=/tmp/lbg_ia_mmo_%r@%h:%p"
)

echo "Rollback client MMO (/mmo/) sur ${VM_USER}@${VM_HOST}…"

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "set -euo pipefail
  cd '${REMOTE_ROOT}'
  if [ ! -d '${REMOTE_RELEASES_DIR}' ]; then
    echo 'ERREUR: dossier releases introuvable: ${REMOTE_RELEASES_DIR}' >&2
    exit 1
  fi

  latest=\$(ls -1dt '${REMOTE_RELEASES_DIR}'/backup_* 2>/dev/null | head -n 1 || true)
  if [ -z \"\${latest}\" ]; then
    echo 'ERREUR: aucun backup trouvé (backup_*) dans mmo_releases' >&2
    exit 2
  fi
  if [ ! -f \"\${latest}/index.html\" ]; then
    echo \"ERREUR: backup sans index.html: \${latest}\" >&2
    exit 3
  fi

  echo \"Backup sélectionné: \${latest}\"
  sudo rm -rf '${REMOTE_DIR}'
  sudo mkdir -p '${REMOTE_DIR}'
  sudo chown -R '${VM_USER}:${VM_USER}' '${REMOTE_DIR}'
  rsync -a --delete \"\${latest}/\" '${REMOTE_DIR}/'
  sudo systemctl restart nginx
  echo 'OK: rollback effectué.'
"

echo "Terminé. Ouvre http://${VM_HOST}:8080/mmo/ puis Ctrl+F5."

