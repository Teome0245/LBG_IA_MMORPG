"""Joueurs en ligne Core3 (lbgemu / bots) — lecture player_snapshots.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from services.lbg_gateway.world_coords import (
        CELL_TO_LOCATION,
        infer_location_id,
        is_cell_local_pos,
        load_location_anchors,
        local_pos_for_interior,
        resolve_world_pos,
    )
except ImportError:
    from world_coords import (  # type: ignore[no-redef]
        CELL_TO_LOCATION,
        infer_location_id,
        is_cell_local_pos,
        load_location_anchors,
        local_pos_for_interior,
        resolve_world_pos,
    )


def _tracked_names() -> set[str]:
    raw = os.environ.get("LBG_GATEWAY_TRACK_PLAYERS", "Gally,Lia,Nix")
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def _load_snapshots(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _players_map(doc: dict[str, Any]) -> dict[str, Any]:
    players = doc.get("players")
    if isinstance(players, dict):
        return players
    return doc if all(isinstance(v, dict) for v in doc.values()) else {}


def _match_tracked(key: str, snap: dict[str, Any], tracked: set[str]) -> bool:
    if not tracked:
        return True
    candidates = [
        key,
        str(snap.get("player", "")),
        str(snap.get("firstname", "")),
    ]
    return any(c.strip().lower() in tracked for c in candidates if c.strip())


def _resolve_player_pos(snap: dict[str, Any], anchors: dict[str, dict[str, float]]) -> list[float]:
    x = float(snap.get("x", 0) or 0)
    y = float(snap.get("y", 0) or 0)
    z = float(snap.get("z", 0) or 0)
    parent = int(snap.get("parent_id", 0) or 0)
    in_interior = snap.get("in_interior") is True or parent > 0
    if in_interior and is_cell_local_pos(x, y, z):
        loc = infer_location_id(cell=parent)
        return resolve_world_pos({"x": x, "y": y, "z": z}, location_id=loc, anchors=anchors, cell=parent)
    if is_cell_local_pos(x, y, z):
        loc = infer_location_id(cell=parent)
        return resolve_world_pos({"x": x, "y": y, "z": z}, location_id=loc, anchors=anchors, cell=parent)
    return [x, y, z]


def build_zone_player_entities(
    *,
    snapshots_path: Path,
    locations_dir: str,
) -> list[dict[str, Any]]:
    """Entités joueur lues depuis ia_bridge (connectés en zone Core3 / lbgemu)."""
    doc = _load_snapshots(snapshots_path)
    if not doc:
        return []
    tracked = _tracked_names()
    anchors = load_location_anchors(locations_dir)
    out: list[dict[str, Any]] = []
    for key, snap in _players_map(doc).items():
        if not isinstance(snap, dict):
            continue
        if not _match_tracked(str(key), snap, tracked):
            continue
        if snap.get("online") is False:
            continue
        first = str(snap.get("firstname") or snap.get("player") or key).strip()
        if not first:
            continue
        parent = int(snap.get("parent_id", 0) or 0)
        lx = float(snap.get("x", 0) or 0)
        ly = float(snap.get("y", 0) or 0)
        lz = float(snap.get("z", 0) or 0)
        pos = _resolve_player_pos(snap, anchors)
        eid = f"player:{first}"
        row: dict[str, Any] = {
            "id": eid,
            "kind": "player",
            "name": first,
            "source": "core3",
            "pos": pos,
            "cell": parent,
            "zone": str(snap.get("zone", "tatooine")),
            "online": True,
        }
        lp = local_pos_for_interior(lx, ly, lz, cell=parent)
        if lp is not None:
            row["local_pos"] = lp
        out.append(row)
    return out
