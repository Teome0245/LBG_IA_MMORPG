#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — durcissement HTTP interne snapshot (mmmorpg_server)
#
# Vérifie:
# - Auth: 401 sans token (si token configuré), 200 avec token
# - Rate-limit: au moins un 429 sous spam (si RL configuré >0)
#
# Usage:
#   bash infra/scripts/smoke_snapshot_auth_rl.sh
#
# Variables :
#   LBG_LAN_HOST_MMO              défaut 192.168.0.245
#   LBG_MMMORPG_INTERNAL_PORT     défaut 8773
#   LBG_SMOKE_NPC_ID              défaut npc:merchant
#   LBG_MMMORPG_INTERNAL_HTTP_TOKEN optionnel (sinon lecture infra/secrets/lbg.env)

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMMORPG_INTERNAL_PORT:-8773}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
TOKEN="${LBG_MMMORPG_INTERNAL_HTTP_TOKEN:-${LBG_MMMORPG_INTERNAL_TOKEN:-}}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEC_FILE="${ROOT_DIR}/infra/secrets/lbg.env"

read_env_var() {
  local key="$1"
  python3 - <<'PY' "$SEC_FILE" "$key"
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not p.exists():
    print("")
    raise SystemExit(0)
pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*\"?(.*?)\"?\s*$")
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    m = pat.match(line)
    if m:
        print(m.group(1).strip())
        raise SystemExit(0)
print("")
PY
}

if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(read_env_var "LBG_MMMORPG_INTERNAL_HTTP_TOKEN")"
fi
RL_RPS="$(read_env_var "MMMORPG_INTERNAL_HTTP_RL_RPS")"
RL_BURST="$(read_env_var "MMMORPG_INTERNAL_HTTP_RL_BURST")"

snap_url="http://${MMO}:${PORT}/internal/v1/npc/${NPC_ID}/lyra-snapshot?trace_id=smoke_auth_rl"

curl_code() {
  # args: extra curl args...
  curl -sS -o /dev/null -w "%{http_code}" "$@" "${snap_url}" || echo "000"
}

echo "== Snapshot auth/rl (mmo=${MMO}:${PORT}, npc=${NPC_ID}) =="
echo "token_present=$([[ -n \"${TOKEN}\" ]] && echo 1 || echo 0) rl_rps=${RL_RPS:-} rl_burst=${RL_BURST:-}"

if [[ -n "${TOKEN}" ]]; then
  echo ""
  echo "== 1) Auth : sans token => 401 =="
  code="$(curl_code)"
  if [[ "${code}" != "401" ]]; then
    echo "ERREUR: attendu 401 sans token, reçu ${code}" >&2
    exit 1
  fi
  echo "OK: 401"

  echo ""
  echo "== 2) Auth : avec token => 200 =="
  code="$(curl_code -H "X-LBG-Service-Token: ${TOKEN}")"
  if [[ "${code}" != "200" ]]; then
    echo "ERREUR: attendu 200 avec token, reçu ${code}" >&2
    exit 1
  fi
  echo "OK: 200"
else
  echo ""
  echo "== Auth : SKIP (pas de token configuré) =="
fi

if [[ -n "${RL_RPS}" && -n "${RL_BURST}" && "${RL_RPS}" != "0" && "${RL_BURST}" != "0" ]]; then
  echo ""
  echo "== 3) Rate-limit : spam => au moins un 429 =="
  hits_429=0
  # Utiliser token si présent, sinon sans.
  hdr=()
  if [[ -n "${TOKEN}" ]]; then hdr=(-H "X-LBG-Service-Token: ${TOKEN}"); fi
  for i in $(seq 1 40); do
    c="$(curl -sS "${hdr[@]}" -o /dev/null -w "%{http_code}" "${snap_url}" || echo "000")"
    if [[ "${c}" == "429" ]]; then
      hits_429=$((hits_429+1))
      break
    fi
  done
  if [[ "${hits_429}" -lt 1 ]]; then
    echo "ERREUR: attendu au moins un 429 (RL activé), aucun 429 observé" >&2
    exit 1
  fi
  echo "OK: 429 observé"
else
  echo ""
  echo "== Rate-limit : SKIP (RL non configuré dans lbg.env) =="
fi

echo ""
echo "Smoke snapshot auth/rl : OK"

