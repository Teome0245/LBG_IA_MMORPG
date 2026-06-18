#!/usr/bin/env bash
# Génère patch_lbg_00.tre (commande client /lbgwe) pour le canal Prime.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ -n "${SWG_ROOT:-}" && -f "${SWG_ROOT}/clients/prime-lbg/datatables/command/client_command_table.iff" ]]; then
  export SWG_SOURCE_IFF="${SWG_ROOT}/clients/prime-lbg/datatables/command/client_command_table.iff"
elif [[ -n "${SWG_ROOT:-}" && -f "${SWG_ROOT}/StarWarsGalaxies/datatables/command/client_command_table.iff" ]]; then
  export SWG_SOURCE_IFF="${SWG_ROOT}/StarWarsGalaxies/datatables/command/client_command_table.iff"
fi

python3 tools/client_patch/build_lbgwe_client_patch.py "$@"

echo ""
echo "Déployer sur VM 245 : bash infra/scripts/install_client_patch_server_245.sh"
echo "Puis côté client Prime : relancer le launchpad (patch HTTP) ou copier patch_lbg_00.tre"
