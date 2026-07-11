"""Helpers lbg-ws/2 — zone_state preview (snapshots → Godot)."""

from __future__ import annotations

import time
from typing import Any


def supported_protos() -> list[str]:
    protos = ["lbg-ws/1", "lbg-ws/2-preview"]
    try:
        from services.lbg_gateway.zone_bridge_feed import read_live_zone_state, zone_bridge_live_enabled

        if zone_bridge_live_enabled() and read_live_zone_state() is not None:
            protos.append("lbg-ws/2")
    except ImportError:
        pass
    return protos


def normalize_proto(raw: str | None) -> str:
    p = (raw or "lbg-ws/1").strip()
    if p in ("lbg-ws/2", "lbg-ws/2-preview", "2"):
        return "lbg-ws/2"
    return "lbg-ws/1"


def entity_to_v2(ent: dict[str, Any]) -> dict[str, Any]:
    pos = ent.get("pos")
    if not isinstance(pos, list) or len(pos) < 3:
        pos = [float(ent.get("x", 0)), float(ent.get("y", 0)), float(ent.get("z", 0))]
    out: dict[str, Any] = {
        "id": str(ent.get("id", ent.get("name", "entity"))),
        "kind": str(ent.get("kind", "npc")),
        "name": str(ent.get("name", "")),
        "pos": [float(pos[0]), float(pos[1]), float(pos[2])],
        "source": "gateway",
    }
    if ent.get("cell") is not None:
        out["cell"] = int(ent["cell"])
    if isinstance(ent.get("local_pos"), list):
        out["local_pos"] = ent["local_pos"]
    if ent.get("appearance"):
        out["appearance"] = ent["appearance"]
    if ent.get("anim"):
        out["anim"] = ent["anim"]
    return out


def build_zone_state_v2(
    *,
    zone: str,
    tick: int,
    entities: list[dict[str, Any]],
    your_character_id: int | None = None,
    removed_entity_ids: list[str] | None = None,
    session_policy: str = "kick_other",
) -> dict[str, Any]:
    v2_entities = [entity_to_v2(e) for e in entities if isinstance(e, dict)]
    payload: dict[str, Any] = {
        "type": "zone_state",
        "proto": "lbg-ws/2",
        "zone": zone,
        "tick": int(tick),
        "server_time_ms": int(time.time() * 1000),
        "entities": v2_entities,
        "session_policy": session_policy,
    }
    if your_character_id is not None:
        payload["your_character_id"] = int(your_character_id)
    if removed_entity_ids:
        payload["removed_entity_ids"] = removed_entity_ids
    return payload


def enter_world_v2(
    *,
    zone: str,
    entities: list[dict[str, Any]],
    your_character_id: int = 1,
    position: list[float] | None = None,
) -> dict[str, Any]:
    base = build_zone_state_v2(
        zone=zone,
        tick=0,
        entities=entities,
        your_character_id=your_character_id,
    )
    base["type"] = "enter_world"
    if position:
        base["position"] = position
    return base
