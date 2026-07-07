#!/usr/bin/env bash
# Harmonise les hostnames LAN LBG (IPs inchangées).
#
#   110 → lbg-ia-ui
#   140 → lbg-backend
#   245 → lbg-mmo-precu
#   246 → lbg-mmo-prime
#
# Usage :
#   bash infra/scripts/set_lan_hostnames.sh --dry-run
#   bash infra/scripts/set_lan_hostnames.sh
#   bash infra/scripts/set_lan_hostnames.sh --host 110
#   bash infra/scripts/set_lan_hostnames.sh --verify-only
#
# Prérequis : ssh lbg@192.168.0.{110,140,245,246} (sudo NOPASSWD ou mot de passe).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VM_USER="${LBG_VM_USER:-lbg}"

declare -A TARGET_NAMES=(
  [110]="lbg-ia-ui"
  [140]="lbg-backend"
  [245]="lbg-mmo-precu"
  [246]="lbg-mmo-prime"
)

HOSTS=(110 140 245 246)
DRY_RUN=0
VERIFY_ONLY=0
FILTER_HOST=""

SSH_OPTS=(
  -o ConnectTimeout=8
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
)

log() { echo "[set_lan_hostnames] $*"; }

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    --host=*) FILTER_HOST="${arg#*=}" ;;
    110|140|245|246) FILTER_HOST="$arg" ;;
    *)
      echo "Option inconnue : $arg (voir --help)" >&2
      exit 1
      ;;
  esac
done

remote_apply() {
  local octet="$1"
  local new_name="$2"
  local lan_ip="192.168.0.${octet}"

  ssh "${SSH_OPTS[@]}" "${VM_USER}@${lan_ip}" bash -s -- "$new_name" "$lan_ip" <<'REMOTE'
set -euo pipefail
NEW="$1"
LAN_IP="$2"
OLD="$(hostname)"

if [[ "$(id -u)" -ne 0 ]]; then
  if ! sudo -n true 2>/dev/null; then
    echo "sudo requis sur ${LAN_IP} (NOPASSWD ou session interactive)" >&2
    exit 1
  fi
  SUDO="sudo -n"
else
  SUDO=""
fi

if [[ "$OLD" == "$NEW" ]]; then
  echo "SKIP ${LAN_IP} déjà ${NEW}"
  exit 0
fi

echo "APPLY ${LAN_IP}: ${OLD} → ${NEW}"

$SUDO hostnamectl set-hostname "$NEW"

if [[ -f /etc/cloud/cloud.cfg ]]; then
  if grep -q '^preserve_hostname:' /etc/cloud/cloud.cfg; then
    $SUDO sed -i 's/^preserve_hostname:.*/preserve_hostname: true/' /etc/cloud/cloud.cfg
  else
    echo "preserve_hostname: true" | $SUDO tee -a /etc/cloud/cloud.cfg >/dev/null
  fi
fi

TMP="$(mktemp)"
$SUDO cp /etc/hosts "$TMP.bak"
$SUDO awk -v new="$NEW" -v ip="$LAN_IP" -v old="$OLD" '
  BEGIN { has12711=0; has_ip=0 }
  /^[[:space:]]*127\.0\.1\.1[[:space:]]/ {
    print "127.0.1.1       " new
    has12711=1
    next
  }
  $1 == ip && $2 == old { print ip "\t" new; has_ip=1; next }
  $1 == ip && $2 == new { has_ip=1 }
  { print }
  END {
    if (!has12711) print "127.0.1.1       " new
    if (!has_ip) print ip "\t" new
  }
' /etc/hosts | $SUDO tee /etc/hosts >/dev/null

hostname
REMOTE
}

remote_verify() {
  local octet="$1"
  local expected="$2"
  local lan_ip="192.168.0.${octet}"
  local got
  got="$(ssh "${SSH_OPTS[@]}" "${VM_USER}@${lan_ip}" 'hostname' 2>/dev/null || echo "?")"
  if [[ "$got" == "$expected" ]]; then
    log "  OK  ${lan_ip} → ${got}"
    return 0
  fi
  log "  KO  ${lan_ip} → ${got} (attendu ${expected})"
  return 1
}

run_hosts() {
  local list=("$@")
  for octet in "${list[@]}"; do
    local name="${TARGET_NAMES[$octet]}"
    if [[ -z "$name" ]]; then
      log "Octet inconnu : $octet"
      continue
    fi
    if [[ "$VERIFY_ONLY" == "1" ]]; then
      remote_verify "$octet" "$name" || true
      continue
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
      local cur
      cur="$(ssh "${SSH_OPTS[@]}" "${VM_USER}@192.168.0.${octet}" 'hostname' 2>/dev/null || echo '?')"
      log "DRY-RUN ${octet}: ${cur} → ${name}"
      continue
    fi
    remote_apply "$octet" "$name"
  done
}

main_hosts=("${HOSTS[@]}")
if [[ -n "$FILTER_HOST" ]]; then
  main_hosts=("$FILTER_HOST")
fi

log "Référence : ${ROOT}/docs/ops_vm_user.md §4"
run_hosts "${main_hosts[@]}"

if [[ "$VERIFY_ONLY" == "1" || "$DRY_RUN" == "1" ]]; then
  exit 0
fi

log "Vérification finale…"
fail=0
for octet in "${main_hosts[@]}"; do
  remote_verify "$octet" "${TARGET_NAMES[$octet]}" || fail=1
done
exit "$fail"
