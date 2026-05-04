#!/usr/bin/env bash
set -euo pipefail
# Wrapper : le dépôt applicatif est `LBG_IA_MMO/` ; ce fichier permet de lancer le smoke depuis la racine du workspace (ex. LBG_IA_MMORPG).
# Les arguments (ex. --desktop-route) et les variables d’environnement sont transmis au script sous LBG_IA_MMO/.

_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ROOT="$(cd "${_HERE}/../.." && pwd)"
_MONO="${_ROOT}/LBG_IA_MMO"
_TARGET="${_MONO}/infra/scripts/smoke_lan_core_desktop.sh"

if [[ ! -f "${_TARGET}" ]]; then
  echo "ERREUR: script introuvable (${_TARGET}). Es-tu à la racine du workspace qui contient LBG_IA_MMO/ ?" >&2
  exit 1
fi

exec bash "${_TARGET}" "$@"
