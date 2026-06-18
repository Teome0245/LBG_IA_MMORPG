"""Boucle autonome Lia — incarnation orchestrateur (tick → Core3 /v1/think)."""

from __future__ import annotations

import os
import time
from typing import Any

from lbg_agents.core3_player_autonomy import player_autonomy_poll_s
from lbg_agents.core3_player_events import peek_latest_inbound_event
from lbg_agents.lia_orchestrator import (
    autonomy_tick as orchestrator_autonomy_tick,
    bot_player_name,
    build_hear_prompt,
    build_proactive_prompt,
    fetch_brain_status,
    fetch_player_snapshot,
    hear_player_message,
    incarnate_player_think,
    _tick_via_orchestrator,
    _tick_via_sidecar,
)


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def lia_autonomy_enabled() -> bool:
    return _truthy(os.environ.get("LBG_CORE3_LIA_AUTONOMY_ENABLED", "0"))


def lia_autonomy_interval_s() -> int:
    raw = os.environ.get("LBG_CORE3_LIA_AUTONOMY_INTERVAL_S", "30").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 30
    return max(15, min(n, 600))


def run_lia_autonomy_loop() -> None:
    """Poll rapide du chat spatial + tours proactifs espacés (population joueurs + PNJ)."""
    from lbg_agents.core3_population_autonomy import run_population_autonomy_loop

    run_population_autonomy_loop()


def lia_autonomy_tick(*, actor_id: str | None = None) -> dict[str, Any]:
    """Un tick : état brain orchestrateur → prompt incarnation → enqueue en jeu."""
    prev = os.environ.get("LBG_CORE3_LIA_ACTOR_ID")
    if actor_id:
        os.environ["LBG_CORE3_LIA_ACTOR_ID"] = actor_id
    try:
        return orchestrator_autonomy_tick()
    finally:
        if actor_id:
            if prev is None:
                os.environ.pop("LBG_CORE3_LIA_ACTOR_ID", None)
            else:
                os.environ["LBG_CORE3_LIA_ACTOR_ID"] = prev
