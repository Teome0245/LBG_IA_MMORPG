#!/usr/bin/env bash
# Lance un joueur IA Core3 déclaré dans /opt/LBG_IA_MMO/content/core3/core3_ia_players.json.
#
# Usage (VM 245) :
#   bash /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_player_vm.sh nix

set -euo pipefail

PLAYER_ID="${1:?player id requis (ex. nix)}"
REGISTRY="${LBG_CORE3_IA_PLAYERS_JSON:-/opt/LBG_IA_MMO/content/core3/core3_ia_players.json}"
BIN_DIR="${CORE3_BIN_DIR:-/opt/lbg-new-mmo-clean/MMOCoreORB/bin}"

eval "$(
  PLAYER_ID="${PLAYER_ID}" REGISTRY="${REGISTRY}" BIN_DIR="${BIN_DIR}" python3 <<'PY'
import json
import os
import shlex
from pathlib import Path

player_id = os.environ["PLAYER_ID"]
registry = Path(os.environ["REGISTRY"])
data = json.loads(registry.read_text())
for row in data.get("players", []):
    if row.get("id") == player_id:
        print("CORE3_IA_BOT_CHARACTER=" + shlex.quote(str(row["firstname"])))
        print("CORE3_CLIENT_ENV_FILE=" + shlex.quote(str(Path(os.environ["BIN_DIR"]) / row["env_file"])))
        print("CORE3_CLIENT_OPTIONS_JSON=" + shlex.quote(str(Path(os.environ["BIN_DIR"]) / row["session_json"])))
        break
else:
    raise SystemExit(f"joueur IA inconnu: {player_id}")
PY
)"

export CORE3_IA_BOT_CHARACTER CORE3_CLIENT_ENV_FILE CORE3_CLIENT_OPTIONS_JSON
exec /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh
