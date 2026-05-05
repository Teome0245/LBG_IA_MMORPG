"""Schémas de messages JSON (Phase 1)."""

from __future__ import annotations

from typing import Any


PROTO = "mmmorpg-ws/1"


def msg_error(message: str) -> dict[str, Any]:
    return {"proto": PROTO, "type": "error", "message": message}


def msg_welcome(
    *,
    player_id: str,
    session_token: str | None = None,
    game_data: dict[str, Any] | None = None,
    planet_id: str,
    world_time_s: float,
    day_fraction: float,
    entities: list[dict[str, Any]],
    locations: list[dict[str, Any]] | None = None,
    npc_reply: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "proto": PROTO,
        "type": "welcome",
        "player_id": player_id,
        "planet_id": planet_id,
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
        "locations": locations or [],
    }
    if isinstance(game_data, dict) and game_data:
        msg["game_data"] = game_data
    if isinstance(session_token, str) and session_token.strip():
        msg["session_token"] = session_token.strip()
    if isinstance(npc_reply, str) and npc_reply.strip():
        msg["npc_reply"] = npc_reply.strip()
    if isinstance(trace_id, str) and trace_id.strip():
        msg["trace_id"] = trace_id.strip()
    return msg


def msg_world_tick(
    *,
    world_time_s: float,
    day_fraction: float,
    entities: list[dict[str, Any]],
    locations: list[dict[str, Any]] | None = None,
    npc_reply: str | None = None,
    trace_id: str | None = None,
    world_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "proto": PROTO,
        "type": "world_tick",
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
        "locations": locations or [],
    }
    if isinstance(npc_reply, str) and npc_reply.strip():
        msg["npc_reply"] = npc_reply.strip()
    if isinstance(trace_id, str) and trace_id.strip():
        msg["trace_id"] = trace_id.strip()
    if isinstance(world_event, dict) and world_event:
        msg["world_event"] = world_event
    return msg
