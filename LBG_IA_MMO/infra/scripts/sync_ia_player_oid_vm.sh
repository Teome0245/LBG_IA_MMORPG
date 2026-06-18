#!/usr/bin/env bash
# Met a jour characterOid dans ia_bridge/*_bot_session.json depuis MariaDB (galaxy 3).
# Usage :
#   bash infra/scripts/sync_ia_player_oid_vm.sh mira
#   LBG_NEW_MMO_VM_HOST=192.168.0.246 DB_HOST=192.168.0.245 bash infra/scripts/sync_ia_player_oid_vm.sh mira

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAYER_ID="${1:?player id (ex. mira)}"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}"
VM_USER="${LBG_VM_USER:-lbg}"
DB_HOST="${LBG_CORE3_DB_HOST:-${LBG_NEW_MMO_VM_HOST:-${LBG_LAN_HOST_CORE3_PRIME:-192.168.0.246}}}"
DB_USER="${LBG_CORE3_DB_USER:-swgemu}"
DB_PASS="${LBG_CORE3_DB_PASS:-123456}"
DB_NAME="${LBG_CORE3_DB_NAME:-swgemu}"
BIN="/opt/lbg-new-mmo-clean/MMOCoreORB/bin"

eval "$(
  PLAYER_ID="${PLAYER_ID}" ROOT_DIR="${ROOT_DIR}" python3 <<'PY'
import json, os, shlex
from pathlib import Path
player_id = os.environ["PLAYER_ID"]
root = Path(os.environ["ROOT_DIR"])
data = json.loads((root / "content/core3/core3_ia_players.json").read_text())
for row in data.get("players", []):
    if row.get("id") == player_id:
        print("FIRSTNAME=" + shlex.quote(str(row["firstname"])))
        print("ACCOUNT=" + shlex.quote(str(row["account"])))
        print("SESSION_REL=" + shlex.quote(str(row["session_json"])))
        break
else:
    raise SystemExit(f"joueur inconnu: {player_id}")
PY
)"

OID="$(
  ssh "${VM_USER}@${DB_HOST}" "mysql -h127.0.0.1 -u${DB_USER} -p${DB_PASS} ${DB_NAME} -N -e \
    \"SELECT c.character_oid FROM accounts a JOIN characters c ON c.account_id=a.account_id \
     WHERE LOWER(a.username)=LOWER('${ACCOUNT}') AND LOWER(c.firstname)=LOWER('${FIRSTNAME}') AND c.galaxy_id=3 LIMIT 1;\" 2>/dev/null" \
    | tr -d '[:space:]'
)"

if [[ -z "${OID}" || "${OID}" == "NULL" ]]; then
  echo "ERROR: perso ${FIRSTNAME} (${ACCOUNT}) introuvable en galaxy 3 sur ${DB_HOST}" >&2
  echo "Creer le personnage en jeu puis relancer ce script." >&2
  exit 2
fi

echo "OID=${OID} pour ${FIRSTNAME} (${ACCOUNT})"

ssh "${VM_USER}@${VM_HOST}" "python3 - <<PY
import json
from pathlib import Path
path = Path('${BIN}') / '${SESSION_REL}'
data = json.loads(path.read_text())
oid = int('${OID}')
data['characterOid'] = oid
for step in data.get('actions', []):
    if step.get('action') == 'selectContext':
        step['characterOid'] = oid
        step.setdefault('galaxyId', 3)
path.write_text(json.dumps(data, indent=2) + '\n')
print('session mise a jour:', path)
PY"

echo "OK — activer : ssh ${VM_USER}@${VM_HOST} 'sudo systemctl enable --now lbg-core3-ia-player@${PLAYER_ID}.service'"
