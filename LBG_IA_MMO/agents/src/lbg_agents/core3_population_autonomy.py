"""Boucle autonomie population — tous les joueurs IA actifs + PNJ pilotes."""

from __future__ import annotations

import os
import time
from typing import Any

from lbg_agents.core3_player_autonomy import player_autonomy_poll_s, player_autonomy_tick
from lbg_agents.core3_players import list_autonomy_players
from lbg_agents.lia_autonomy import lia_autonomy_interval_s, lia_autonomy_tick
from lbg_agents.lia_orchestrator import bot_player_name


def population_autonomy_enabled() -> bool:
    return os.environ.get("LBG_CORE3_POPULATION_AUTONOMY_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def run_population_autonomy_loop() -> None:
    from lbg_agents.core3_bot_connection import ensure_ia_bots_online
    from lbg_agents.core3_npc_autonomy import npc_autonomy_tick_all

    interval = lia_autonomy_interval_s()
    poll = player_autonomy_poll_s()
    next_proactive = 0.0
    lia_name = bot_player_name().lower()

    while True:
        from lbg_agents.core3_player_events import peek_latest_inbound_event

        social_event, _ = peek_latest_inbound_event("lia", bot_player_name())
        now = time.monotonic()
        if social_event is not None:
            print(lia_autonomy_tick(), flush=True)
            next_proactive = now + interval
            time.sleep(poll)
            continue

        if now >= next_proactive:
            ensure_ia_bots_online()
            print(lia_autonomy_tick(), flush=True)
            for player in list_autonomy_players():
                if player.firstname.lower() == lia_name:
                    continue
                try:
                    print(player_autonomy_tick(player.id, via="sidecar"), flush=True)
                except KeyError:
                    pass
            print(npc_autonomy_tick_all(now=now), flush=True)
            next_proactive = now + interval
        time.sleep(poll)


def population_autonomy_status() -> dict[str, Any]:
    return {
        "enabled": population_autonomy_enabled(),
        "players": [p.id for p in list_autonomy_players()],
        "interval_s": lia_autonomy_interval_s(),
    }
