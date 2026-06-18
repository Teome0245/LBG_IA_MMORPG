#!/usr/bin/env bash
# Reconnexion joueurs IA (Lia/Nix/Mira/Kael) via sidecar — appele par systemd timer.
set -euo pipefail

export PYTHONPATH="/opt/LBG_IA_MMO/agents/src${PYTHONPATH:+:${PYTHONPATH}}"

if ! python3 -c "import httpx" 2>/dev/null; then
  echo "httpx manquant — installer python3-httpx sur la VM Prime" >&2
  exit 1
fi

exec python3 -c "
from lbg_agents.core3_bot_connection import ensure_ia_bots_online
import json
print(json.dumps(ensure_ia_bots_online(), ensure_ascii=False))
"
