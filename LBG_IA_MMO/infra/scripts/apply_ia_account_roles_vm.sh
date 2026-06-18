#!/usr/bin/env bash
# Applique account_admin_level depuis core3_ia_players.json (apres rebuild Prime).
#
# Usage sur la VM Prime :
#   bash infra/scripts/apply_ia_account_roles_vm.sh
#   bash infra/scripts/apply_ia_account_roles_vm.sh --dry-run

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAYERS_JSON="${ROOT_DIR}/content/core3/core3_ia_players.json"
DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
  esac
done

export PLAYERS_JSON DRY ROOT_DIR
python3 <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
players_path = Path(os.environ["PLAYERS_JSON"])
dry = os.environ.get("DRY", "0") == "1"
data = json.loads(players_path.read_text(encoding="utf-8"))
rows = [r for r in data.get("players", []) if isinstance(r, dict)]
sys.path.insert(0, str(root / "tools" / "core3_account_admin"))
import core3_account_admin as adm

if not os.environ.get("CORE3_DB_PASS") and os.environ.get("CORE3_DB_SECRET"):
    os.environ["CORE3_DB_PASS"] = os.environ["CORE3_DB_SECRET"]

updated = 0
accounts_payload = adm.list_accounts()
all_accounts = accounts_payload.get("accounts") if isinstance(accounts_payload, dict) else []
for row in rows:
    level = row.get("account_admin_level")
    if level is None:
        continue
    username = str(row.get("account") or "").strip()
    if not username:
        continue
    lvl = adm.normalize_admin_level(int(level))
    match = None
    for acc in all_accounts:
        if str(acc.get("username") or "").lower() == username.lower():
            match = acc
            break
    if match is None:
        print(f"SKIP {username}: compte introuvable", file=sys.stderr)
        continue
    if dry:
        print(f"DRY {username} -> admin_level {lvl}")
        continue
    try:
        adm.update_account(
            str(match["server_id"]),
            int(match["account_id"]),
            lvl,
            None,
            None,
        )
        print(f"OK {username} -> admin_level {lvl} ({adm.level_label(lvl)})")
        updated += 1
    except Exception as exc:
        print(f"SKIP {username}: {exc}", file=sys.stderr)

print(f"done updated={updated} dry={dry}")
PY
