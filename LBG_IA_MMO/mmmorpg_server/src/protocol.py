"""Schémas de messages JSON (Phase 1)."""

from __future__ import annotations

from typing import Any


def msg_error(message: str) -> dict[str, Any]:
    return {"type": "error", "message": message}


def msg_welcome(
    *,
    player_id: str,
    planet_id: str,
    world_time_s: float,
    day_fraction: float,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "welcome",
        "player_id": player_id,
        "planet_id": planet_id,
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
    }


def msg_world_tick(
    *,
    world_time_s: float,
    day_fraction: float,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "world_tick",
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
    }
