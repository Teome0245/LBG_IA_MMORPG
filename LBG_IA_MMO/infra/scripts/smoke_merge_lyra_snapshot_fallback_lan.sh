#!/usr/bin/env bash
set -euo pipefail

# Smoke LAN — fallback backend : snapshot interne `mmmorpg` KO → `mmo_server`
#
# Vérifie que `merge_mmo_lyra_if_configured` retombe sur `GET /v1/world/lyra`
# (meta.source = mmo_world) lorsque `LBG_MMMORPG_INTERNAL_HTTP_URL` pointe vers
# un port TCP fermé (échec rapide), tout en conservant `LBG_MMO_SERVER_URL`
# depuis `/etc/lbg-ia-mmo.env` sur la VM core.
#
# Prérequis :
# - `mmo_server` joignable depuis le poste de dev sur ${LBG_LAN_HOST_MMO}:8050
#   (systemd `lbg-mmo-server` écoute 0.0.0.0 en prod LAN)
# - SSH vers la VM core (BatchMode)
#
# Usage :
#   bash infra/scripts/smoke_merge_lyra_snapshot_fallback_lan.sh
#
# Variables :
#   LBG_LAN_HOST_CORE défaut 192.168.0.140
#   LBG_LAN_HOST_MMO  défaut 192.168.0.245
#   LBG_VM_USER       défaut lbg
#   LBG_SMOKE_NPC_ID  défaut npc:merchant

CORE="${LBG_LAN_HOST_CORE:-192.168.0.140}"
MMO="${LBG_LAN_HOST_MMO:-192.168.0.245}"
VM_USER="${LBG_VM_USER:-lbg}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"

echo "== 0) Pré-check LAN : mmo_server healthz (mmo=${MMO}:8050) =="
code="$(
  curl -sS --connect-timeout 2 --max-time 4 -o /dev/null -w "%{http_code}" \
    "http://${MMO}:8050/healthz" || echo "000"
)"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: mmo_server non joignable depuis ce poste (HTTP ${code})." >&2
  echo "Indice: déployer l'unité systemd \`lbg-mmo-server\` (bind 0.0.0.0:8050) sur la VM MMO." >&2
  exit 1
fi
echo "OK: mmo_server healthz=200"

echo ""
echo "== 1) SSH core (${VM_USER}@${CORE}) : merge avec snapshot interne forcé KO =="
ssh -o BatchMode=yes -o ConnectTimeout=4 "${VM_USER}@${CORE}" \
  "NPC_ID='${NPC_ID}' /bin/bash -s" <<'EOS'
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /etc/lbg-ia-mmo.env
set +a

export LBG_MMMORPG_INTERNAL_HTTP_URL="http://127.0.0.1:9"

/opt/LBG_IA_MMO/.venv/bin/python - <<'PY'
import asyncio
import os

from services.mmo_lyra_sync import merge_mmo_lyra_if_configured

npc = os.environ["NPC_ID"].strip()
assert npc, "NPC_ID vide"


async def main() -> None:
    ctx: dict = {"world_npc_id": npc, "_trace_id": "smoke_merge_fallback"}
    await merge_mmo_lyra_if_configured(ctx)
    ly = ctx.get("lyra")
    assert isinstance(ly, dict), f"lyra attendu dict, reçu {type(ly).__name__}"
    meta = ly.get("meta")
    assert isinstance(meta, dict), f"lyra.meta attendu dict, reçu {type(meta).__name__}"
    src = (meta.get("source") or "").strip()
    assert src == "mmo_world", f"meta.source attendu mmo_world, reçu {src!r}"
    print("OK: fallback mmo_server (meta.source=mmo_world)")


asyncio.run(main())
PY
EOS

echo ""
echo "Smoke merge Lyra snapshot fallback (LAN) : OK"
