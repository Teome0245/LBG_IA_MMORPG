"""
Sérialisation JSON de ``WorldState`` (reprise au boot, sauvegarde périodique).

Schéma : ``schema_version`` 1 — évolutif pour migrations futures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from entities.location import Location
from entities.npc import Npc
from lyra_engine.gauges import GaugesState
from world.state import WorldState

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _clamp_rep(v: object) -> int:
    try:
        i = int(v)  # accepte str/int/float
    except Exception:
        return 0
    if i < -100:
        return -100
    if i > 100:
        return 100
    return i


def world_state_to_dict(ws: WorldState) -> dict[str, Any]:
    locations_list = []
    for loc in getattr(ws, "locations", {}).values():
        if not loc:
            continue
        locations_list.append(
            {
                "id": loc.id,
                "name": loc.name,
                "type": loc.type,
                "parent_id": loc.parent_id,
                "tags": list(loc.tags or []),
                "geometry": dict(loc.geometry or {}),
            }
        )
    locations_list.sort(key=lambda x: x["id"])

    npcs_list = []
    for npc in ws.npcs.values():
        g = npc.gauges
        npcs_list.append(
            {
                "id": npc.id,
                "name": npc.name,
                "role": npc.role,
                "reputation_value": _clamp_rep(getattr(npc, "reputation_value", 0)),
                "situation": getattr(npc, "situation", {}) or {},
                "goals": list(getattr(npc, "goals", []) or []),
                "gauges": {
                    "hunger": g.hunger,
                    "thirst": g.thirst,
                    "fatigue": g.fatigue,
                },
            }
        )
    npcs_list.sort(key=lambda x: x["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "now_s": ws.now_s,
        "locations": locations_list,
        "npcs": npcs_list,
    }


def world_state_from_dict(data: dict[str, Any]) -> WorldState:
    if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    now_s = float(data["now_s"])
    raw_locations = data.get("locations") or []
    locations: dict[str, Location] = {}
    if isinstance(raw_locations, list):
        for item in raw_locations:
            if not isinstance(item, dict):
                continue
            lid = str(item.get("id", "")).strip()
            if not lid:
                continue
            tags = item.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            geom = item.get("geometry") or {}
            if not isinstance(geom, dict):
                geom = {}
            locations[lid] = Location(
                id=lid,
                name=str(item.get("name", lid)),
                type=str(item.get("type", "unknown")),
                parent_id=item.get("parent_id", None),
                tags=[str(x) for x in tags if x is not None],
                geometry=geom,
            )
    raw_npcs = data["npcs"]
    if not isinstance(raw_npcs, list):
        raise ValueError("npcs must be a list")
    npcs: dict[str, Npc] = {}
    for item in raw_npcs:
        if not isinstance(item, dict):
            continue
        gid = str(item["id"])
        gg = item.get("gauges") or {}
        situation = item.get("situation") or {}
        if not isinstance(situation, dict):
            situation = {}
        goals = item.get("goals") or []
        if not isinstance(goals, list):
            goals = []
        rep = _clamp_rep(item.get("reputation_value", 0))
        npcs[gid] = Npc(
            id=gid,
            name=str(item.get("name", gid)),
            role=str(item.get("role", "unknown")),
            reputation_value=rep,
            situation=situation,
            goals=[str(x) for x in goals if x is not None],
            gauges=GaugesState(
                hunger=float(gg.get("hunger", 0.0)),
                thirst=float(gg.get("thirst", 0.0)),
                fatigue=float(gg.get("fatigue", 0.0)),
            ),
        )
    if not npcs:
        raise ValueError("no npcs in snapshot")
    return WorldState(now_s=now_s, npcs=npcs, locations=locations)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_world_state(path: Path, ws: WorldState) -> None:
    atomic_write_json(path, world_state_to_dict(ws))


def load_world_state(path: Path) -> WorldState | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return world_state_from_dict(data)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("impossible de charger l’état monde depuis %s : %s", path, e)
        return None
