#!/usr/bin/env python3
"""Boucle autonomie générique d'un joueur IA Core3 (Phase G)."""

from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_AGENTS_SRC = os.path.join(_REPO, "agents", "src")
if _AGENTS_SRC not in sys.path:
    sys.path.insert(0, _AGENTS_SRC)

from lbg_agents.core3_player_autonomy import (  # noqa: E402
    player_autonomy_enabled,
    player_autonomy_interval_s,
    run_player_autonomy_loop,
)


def main(argv: list[str]) -> int:
    player_id = (argv[1] if len(argv) > 1 else os.environ.get("LBG_CORE3_IA_PLAYER_ID", "")).strip()
    if not player_id:
        print("LBG_CORE3_IA_PLAYER_ID requis (ex. nix)", file=sys.stderr)
        return 2
    if not player_autonomy_enabled():
        print("LBG_CORE3_PLAYER_AUTONOMY_ENABLED=0 — rien à faire.", file=sys.stderr)
        return 0
    interval = player_autonomy_interval_s()
    print(f"core3_player_autonomy: player={player_id} interval={interval}s")
    run_player_autonomy_loop(player_id)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
