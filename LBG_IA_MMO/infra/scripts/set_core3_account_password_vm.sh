#!/usr/bin/env bash
# Met à jour le mot de passe d'un compte Core3 (hash SWGEmu).
#
# Usage :
#   CORE3_ACCOUNT_USER=Bot_IA CORE3_ACCOUNT_PASSWORD=lbgiabot \
#     bash infra/scripts/set_core3_account_password_vm.sh

set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
USER_NAME="${CORE3_ACCOUNT_USER:-Bot_IA}"
PASS="${CORE3_ACCOUNT_PASSWORD:?CORE3_ACCOUNT_PASSWORD requis}"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<REMOTE
set -euo pipefail
export USER_NAME='${USER_NAME}'
export PASS='${PASS}'
python3 <<'PY'
import hashlib, os, random, subprocess, sys

def hash_password(password: str, salt: str) -> str:
    secret = os.environ.get("CORE3_DB_SECRET", "swgemus3cr37!")
    return hashlib.sha256((secret + password + salt).encode()).hexdigest()

user = os.environ["USER_NAME"]
pwd = os.environ["PASS"]
salt = "".join(random.choice("0123456789abcdef") for _ in range(32))
hp = hash_password(pwd, salt)

subprocess.run(
    [
        "mysql", "-h", "127.0.0.1", "-uswgemu", "-p123456", "swgemu", "-e",
        f"UPDATE accounts SET password='{hp}', salt='{salt}' WHERE username='{user}';",
    ],
    check=True,
)
print(f"Mot de passe mis à jour pour {user}")
PY
REMOTE
