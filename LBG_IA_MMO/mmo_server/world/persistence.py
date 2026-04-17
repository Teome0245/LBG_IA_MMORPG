"""
Sérialisation JSON de ``WorldState`` (reprise au boot, sauvegarde périodique).

Schéma : ``schema_version`` 1 — évolutif pour migrations futures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

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
    npcs_list = []
    for npc in ws.npcs.values():
        g = npc.gauges
        npcs_list.append(
            {
                "id": npc.id,
                "name": npc.name,
                "role": npc.role,
                "reputation_value": _clamp_rep(getattr(npc, "reputation_value", 0)),
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
        "npcs": npcs_list,
    }


def world_state_from_dict(data: dict[str, Any]) -> WorldState:
    if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    now_s = float(data["now_s"])
    raw_npcs = data["npcs"]
    if not isinstance(raw_npcs, list):
        raise ValueError("npcs must be a list")
    npcs: dict[str, Npc] = {}
    for item in raw_npcs:
        if not isinstance(item, dict):
            continue
        gid = str(item["id"])
        gg = item.get("gauges") or {}
        rep = _clamp_rep(item.get("reputation_value", 0))
        npcs[gid] = Npc(
            id=gid,
            name=str(item.get("name", gid)),
            role=str(item.get("role", "unknown")),
            reputation_value=rep,
            gauges=GaugesState(
                hunger=float(gg.get("hunger", 0.0)),
                thirst=float(gg.get("thirst", 0.0)),
                fatigue=float(gg.get("fatigue", 0.0)),
            ),
        )
    if not npcs:
        raise ValueError("no npcs in snapshot")
    return WorldState(now_s=now_s, npcs=npcs)


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
