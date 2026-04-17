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
    npc_reply: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": "welcome",
        "player_id": player_id,
        "planet_id": planet_id,
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
    }
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
    npc_reply: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": "world_tick",
        "world_time_s": world_time_s,
        "day_fraction": day_fraction,
        "entities": entities,
    }
    if isinstance(npc_reply, str) and npc_reply.strip():
        msg["npc_reply"] = npc_reply.strip()
    if isinstance(trace_id, str) and trace_id.strip():
        msg["trace_id"] = trace_id.strip()
    return msg
