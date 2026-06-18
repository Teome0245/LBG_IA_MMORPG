#!/usr/bin/env bash
# Phase A pont IA : Serveur Prime (core3-clean) + Tatooine + Bot_IA + systemd sidecar.
#
# Usage :
#   bash infra/scripts/setup_core3_ia_prime_phase_a_vm.sh
#   CORE3_IA_BOT_PASSWORD='MonMotDePasse' bash infra/scripts/setup_core3_ia_prime_phase_a_vm.sh
#   bash infra/scripts/setup_core3_ia_prime_phase_a_vm.sh --no-restart   # sans redémarrer core3-clean

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.246}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
BOT_USER="${CORE3_IA_BOT_NAME:-Bot_IA}"
BOT_PASS="${CORE3_IA_BOT_PASSWORD:-lbgiabot}"
DO_RESTART=1

for arg in "$@"; do
  case "$arg" in
    --no-restart) DO_RESTART=0 ;;
  esac
done

echo "=== Phase A — Pont IA Prime / Tatooine → ${VM_USER}@${VM_HOST} ==="

bash "${ROOT_DIR}/infra/scripts/deploy_core3_ia_bridge_vm.sh" --no-restart
# Pas de restriction de planètes (défaut config.lua)
CORE3_ZONES_ENABLED= bash "${ROOT_DIR}/infra/scripts/apply_core3_clean_zones_vm.sh"

# Compte Bot_IA + mot de passe (hash SWGEmu)
ssh "${VM_USER}@${VM_HOST}" "bash -s" <<REMOTE
set -euo pipefail
export CORE3_DB_HOST=127.0.0.1 CORE3_DB_USER=swgemu CORE3_DB_PASS=123456 CORE3_DB_NAME=swgemu
export CORE3_DB_SECRET=swgemus3cr37!
BOT_USER='${BOT_USER}'
BOT_PASS='${BOT_PASS}'

python3 <<'PY'
import hashlib, os, random, subprocess, sys

def db_secret():
    return os.environ.get("CORE3_DB_SECRET", "swgemus3cr37!")

def hash_password(password: str, salt: str) -> str:
    payload = db_secret() + password + salt
    return hashlib.sha256(payload.encode()).hexdigest()

def mysql_exec(sql: str) -> None:
    cmd = [
        "mysql", "-h", os.environ["CORE3_DB_HOST"],
        "-u", os.environ["CORE3_DB_USER"],
        f"-p{os.environ['CORE3_DB_PASS']}",
        os.environ["CORE3_DB_NAME"], "-e", sql,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

user = os.environ["BOT_USER"]
pwd = os.environ["BOT_PASS"]
salt = "".join(random.choice("0123456789abcdef") for _ in range(32))
hp = hash_password(pwd, salt)

mysql_exec(
    f"INSERT INTO accounts (username, password, salt, account_id, station_id, admin_level, active) "
    f"SELECT '{user}', '{hp}', '{salt}', COALESCE(MAX(account_id), 0) + 1, 0, 0, 1 FROM accounts "
    f"WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE username = '{user}');"
)

row = subprocess.run(
    [
        "mysql", "-N", "-h", os.environ["CORE3_DB_HOST"],
        "-u", os.environ["CORE3_DB_USER"], f"-p{os.environ['CORE3_DB_PASS']}",
        os.environ["CORE3_DB_NAME"], "-e",
        f"SELECT account_id FROM accounts WHERE username='{user}' LIMIT 1;",
    ],
    check=True, capture_output=True, text=True,
)
aid = row.stdout.strip()
if not aid:
    sys.exit("compte Bot_IA introuvable")
mysql_exec(
    f"UPDATE accounts SET password='{hp}', salt='{salt}', admin_level=0, active=1 "
    f"WHERE username='{user}';"
)
print(f"Compte {user} OK (account_id={aid}, admin_level=0)")
PY
REMOTE

# systemd sidecar
scp -q "${ROOT_DIR}/infra/systemd/lbg-core3-ia-sidecar.service" \
  "${VM_USER}@${VM_HOST}:/tmp/lbg-core3-ia-sidecar.service"

ssh "${VM_USER}@${VM_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
sudo cp /tmp/lbg-core3-ia-sidecar.service /etc/systemd/system/
sudo mkdir -p /etc/lbg-core3-ia.env
if [[ ! -f /etc/lbg-core3-ia.env ]]; then
  sudo tee /etc/lbg-core3-ia.env >/dev/null <<'ENV'
# Pont IA Serveur Prime — Tatooine (id zone Core3)
CORE3_IA_ZONE=tatooine
CORE3_IA_BOT_NAME=Bot_IA
CORE3_IA_BOT_CHARACTER=Lia
# CORE3_IA_BOT_PASSWORD=...  # uniquement pour setup_core3_ia_prime_phase_a_vm.sh
# LBG_DIALOGUE_LLM_BASE_URL=http://192.168.0.110:11434/v1
ENV
fi
sudo systemctl daemon-reload
sudo systemctl enable lbg-core3-ia-sidecar.service
sudo systemctl restart lbg-core3-ia-sidecar.service
sleep 1
systemctl is-active lbg-core3-ia-sidecar.service
curl -s http://127.0.0.1:8791/healthz
echo
REMOTE

if [[ "${DO_RESTART}" == "1" ]]; then
  bash "${ROOT_DIR}/infra/scripts/restart_core3_prime_vm.sh"
fi

echo ""
echo "Smoke (Bot_IA doit être connecté sur Prime/Tatooine pour le message en jeu) :"
ssh "${VM_USER}@${VM_HOST}" "curl -s -X POST http://127.0.0.1:8791/v1/enqueue -H 'Content-Type: application/json' \
  -d '{\"action\":\"say\",\"player\":\"${BOT_USER}\",\"message\":\"Pont IA Prime Tatooine OK\"}'"
echo ""
echo "Login client : galaxie « LBG MMO Serveur Prime », user ${BOT_USER}, pass ${BOT_PASS}"
echo "Doc : ${ROOT_DIR}/docs/core3_ia_prime_tatooine.md"
