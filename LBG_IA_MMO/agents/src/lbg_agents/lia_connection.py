"""Connexion headless Lia (core3client) via sidecar VM Prime."""

from __future__ import annotations

from typing import Any

from lbg_agents.core3_bot_connection import (
    bot_auto_connect_enabled as lia_auto_connect_enabled,
    bot_connect_wait_s as lia_connect_wait_s,
    connect_player,
    ensure_player_connected as ensure_lia_connected,
    is_player_online as is_lia_online,
)
from lbg_agents.lia_orchestrator import bot_player_name


def is_lia_online(player: str | None = None) -> bool:
    return is_player_online(player or bot_player_name())


def connect_lia(
    *,
    wait: bool = True,
    wait_s: int | None = None,
    force_restart: bool = False,
) -> dict[str, Any]:
    return connect_player(
        "lia",
        wait=wait,
        wait_s=wait_s,
        force_restart=force_restart,
    )
