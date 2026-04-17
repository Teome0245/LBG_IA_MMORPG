#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — seed PNJ mmo_server : chaque npc_id du seed doit répondre à /v1/world/lyra
#
# Usage:
#   bash infra/scripts/smoke_mmo_seed_npcs_lan.sh
#
# Variables :
#   LBG_LAN_HOST_MMO défaut 192.168.0.245
#   LBG_MMO_HTTP_PORT défaut 8050
#   LBG_MMO_SEED_PATH défaut mmo_server/world/seed_data/world_initial.json (local workspace)
#

MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
PORT="${LBG_MMO_HTTP_PORT:-8050}"
SEED="${LBG_MMO_SEED_PATH:-mmo_server/world/seed_data/world_initial.json}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEED_PATH="${ROOT_DIR}/${SEED}"

if [[ ! -f "${SEED_PATH}" ]]; then
  echo "ERREUR: seed introuvable: ${SEED_PATH}" >&2
  exit 1
fi

echo "== 0) healthz mmo_server (${MMO}:${PORT}) =="
code="$(
  curl -sS --connect-timeout 2 --max-time 4 -o /dev/null -w "%{http_code}" \
    "http://${MMO}:${PORT}/healthz" || echo "000"
)"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: mmo_server non joignable (HTTP ${code}) : http://${MMO}:${PORT}/healthz" >&2
  exit 1
fi
echo "OK: healthz=200"

echo ""
echo "== 1) npc_ids du seed =="
mapfile -t npc_ids < <(
  python3 - <<'PY' "${SEED_PATH}"
import json, sys
path = sys.argv[1]
data = json.loads(open(path, "r", encoding="utf-8").read())
ids = []
for npc in (data.get("npcs") or []):
    if isinstance(npc, dict):
        gid = str(npc.get("id") or "").strip()
        if gid:
            ids.append(gid)
ids = sorted(set(ids))
for gid in ids:
    print(gid)
PY
)

if [[ "${#npc_ids[@]}" -lt 1 ]]; then
  echo "ERREUR: aucun npc_id trouvé dans le seed" >&2
  exit 1
fi

printf "OK: %s PNJ\n" "${#npc_ids[@]}"

echo ""
echo "== 2) /v1/world/lyra (un par PNJ) =="

# Note : en LAN, `mmo_server` peut charger un état persisté (LBG_MMO_STATE_PATH) au lieu du seed.
# Dans ce cas, de nouveaux PNJ ajoutés au seed peuvent répondre 404 tant que l’état n’est pas reset.
#
# Par défaut on exige seulement le socle historique pour éviter des faux négatifs en prod LAN.
# Pour rendre ce smoke strict (tous les PNJ du seed doivent répondre), définir :
#   LBG_SMOKE_STRICT=1
STRICT="${LBG_SMOKE_STRICT:-0}"
required_ids=("npc:smith" "npc:merchant" "npc:innkeeper" "npc:guard" "npc:scribe")
required_set=" ${required_ids[*]} "

fail=0
missing_optional=0
missing_required=0
for npc_id in "${npc_ids[@]}"; do
  url="http://${MMO}:${PORT}/v1/world/lyra?npc_id=${npc_id}"
  code="$(
    curl -sS --connect-timeout 2 --max-time 6 -o /dev/null -w "%{http_code}" \
      "${url}" || echo "000"
  )"
  if [[ "${code}" != "200" ]]; then
    if [[ "${required_set}" == *" ${npc_id} "* ]]; then
      echo "KO: ${npc_id} (HTTP ${code})"
      missing_required=$((missing_required + 1))
      fail=1
    else
      echo "WARN: ${npc_id} absent côté serveur (HTTP ${code})"
      missing_optional=$((missing_optional + 1))
      if [[ "${STRICT}" == "1" ]]; then
        fail=1
      fi
    fi
  else
    echo "OK: ${npc_id}"
  fi
done

if [[ "${fail}" -ne 0 ]]; then
  echo "" >&2
  if [[ "${missing_required}" -gt 0 ]]; then
    echo "ERREUR: au moins un PNJ *requis* ne répond pas via /v1/world/lyra" >&2
  else
    echo "ERREUR: mode strict activé et au moins un PNJ du seed est absent via /v1/world/lyra" >&2
  fi
  echo "" >&2
  echo "Hint: si la VM MMO charge un état persisté, reset l’état (ou change LBG_MMO_STATE_PATH) pour recharger le seed." >&2
  exit 1
fi

echo ""
if [[ "${missing_optional}" -gt 0 ]]; then
  echo "Note: ${missing_optional} PNJ du seed sont absents côté serveur (état persisté probable)."
fi
echo "Smoke mmo seed PNJ (LAN) : OK"

