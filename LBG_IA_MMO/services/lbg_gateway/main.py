#!/usr/bin/env python3
"""Gateway WebSocket lbg-ws/1 — Core3 Prime snapshots (v0)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

try:
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosedOK
except ImportError:
    raise SystemExit("pip install websockets") from None

try:
    from services.lbg_gateway.catalog_context import build_dialogue_context
    from services.lbg_gateway.dialogue_ia import (
        PLACEHOLDER_ENABLED,
        fetch_npc_reply,
        ia_configured,
        placeholder_reply,
    )
    from services.lbg_gateway.world_coords import (
        infer_location_id,
        load_location_anchors,
        local_pos_for_interior,
        resolve_world_pos,
    )
    from services.lbg_gateway.pending_bridge import (
        inject_enabled,
        inject_move_to,
        inject_player_name,
        pending_path,
    )
    from services.lbg_gateway.roster_filter import allow_roster_npc, roster_policies_from_catalog
    from services.lbg_gateway.zone_players import build_zone_player_entities
except ImportError:
    from catalog_context import build_dialogue_context  # type: ignore[no-redef]
    from dialogue_ia import (  # type: ignore[no-redef]
        PLACEHOLDER_ENABLED,
        fetch_npc_reply,
        ia_configured,
        placeholder_reply,
    )
    from world_coords import (  # type: ignore[no-redef]
        infer_location_id,
        load_location_anchors,
        local_pos_for_interior,
        resolve_world_pos,
    )
    from pending_bridge import (  # type: ignore[no-redef]
        inject_enabled,
        inject_move_to,
        inject_player_name,
        pending_path,
    )
    from roster_filter import allow_roster_npc, roster_policies_from_catalog  # type: ignore[no-redef]
    from zone_players import build_zone_player_entities  # type: ignore[no-redef]

LOG = logging.getLogger("lbg_gateway")
HOST = os.environ.get("LBG_GATEWAY_HOST", "0.0.0.0")
PORT = int(os.environ.get("LBG_GATEWAY_PORT", "50000"))
TICK_S = float(os.environ.get("LBG_GATEWAY_TICK_S", "2.0"))
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = Path(
    os.environ.get(
        "LBG_GATEWAY_SNAPSHOTS",
        str(ROOT / "content/core3/ia_bridge/npc_snapshots.json"),
    )
)
CATALOG = Path(os.environ.get("LBG_GATEWAY_CATALOG", str(ROOT / "content/core3/core3_npc_catalog.json")))
PLAYER_SNAPSHOTS = Path(
    os.environ.get(
        "LBG_GATEWAY_PLAYER_SNAPSHOTS",
        str(SNAPSHOTS.parent / "player_snapshots.json"),
    )
)
_GW_DIR = Path(__file__).resolve().parent
_LOC_DEFAULT = _GW_DIR / "locations"
if not _LOC_DEFAULT.is_dir():
    _LOC_DEFAULT = ROOT / "content/core3/locations"
LOCATIONS_DIR = Path(os.environ.get("LBG_GATEWAY_LOCATIONS", str(_LOC_DEFAULT)))


def _default_player_spawn() -> list[float]:
    anchors = load_location_anchors(str(LOCATIONS_DIR))
    bar = anchors.get("mos_eisley_cantina_bar")
    if bar:
        return cell_to_world({"x": 10.0, "y": 1.0, "z": 3.0}, bar)
    return [3526.0, 5.0, -4799.0]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _catalog_pilots() -> dict[str, dict[str, Any]]:
    doc = _load_json(CATALOG)
    out: dict[str, dict[str, Any]] = {}
    for roster in doc.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        for slot in roster.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            pid = str(slot.get("pilot_id", "")).strip()
            binding = slot.get("binding") or {}
            if pid:
                out[pid] = {
                    "display_name": slot.get("display_name", pid),
                    "binding": binding,
                    "location_id": str(roster.get("location_id", "")).strip(),
                    "roster_id": str(roster.get("roster_id", "")).strip(),
                }
    return out


def _roster_policies() -> dict[str, str]:
    return roster_policies_from_catalog(_load_json(CATALOG))


def _maybe_inject_move(pos: list[float]) -> None:
    path = pending_path()
    if path is None or not inject_enabled():
        return
    if len(pos) < 3:
        return
    try:
        inject_move_to(
            path,
            inject_player_name(),
            float(pos[0]),
            float(pos[1]),
            float(pos[2]),
        )
    except OSError:
        LOG.warning("inject move failed path=%s", path)


def _npc_entity_row(
    *,
    pilot_id: str,
    name: str,
    x: float,
    y: float,
    z: float,
    cell: int,
    location_id: str,
    anchors: dict[str, dict[str, float]],
) -> dict[str, Any]:
    loc = infer_location_id(location_id=location_id, cell=cell)
    pos = resolve_world_pos(
        {"x": x, "y": y, "z": z},
        location_id=loc,
        anchors=anchors,
        cell=cell,
    )
    row: dict[str, Any] = {
        "id": pilot_id,
        "kind": "npc",
        "name": name,
        "pilot_id": pilot_id,
        "pos": pos,
        "cell": cell,
    }
    lp = local_pos_for_interior(x, y, z, cell=cell)
    if lp is not None:
        row["local_pos"] = lp
    return row


def _build_entities(player_pos: list[float]) -> list[dict[str, Any]]:
    snaps = _load_json(SNAPSHOTS)
    pilots = _catalog_pilots()
    policies = _roster_policies()
    roster_active: dict[str, str] = {}
    anchors = load_location_anchors(str(LOCATIONS_DIR))
    entities: list[dict[str, Any]] = []
    for zp in build_zone_player_entities(
        snapshots_path=PLAYER_SNAPSHOTS,
        locations_dir=str(LOCATIONS_DIR),
    ):
        entities.append(zp)
    entities.append(
        {
            "id": 1,
            "kind": "player",
            "name": "Vous (Godot)",
            "source": "gateway",
            "pos": player_pos,
            "cell": 0,
        }
    )
    eid = 2
    seen: set[str] = set()
    for pilot_id, snap in snaps.items():
        if not isinstance(snap, dict):
            continue
        if snap.get("online") is False:
            continue
        seen.add(pilot_id)
        meta = pilots.get(pilot_id, {})
        if not allow_roster_npc(pilot_id, meta, policies, roster_active):
            continue
        name = str(snap.get("display_name") or meta.get("display_name") or pilot_id)
        x = float(snap.get("x", snap.get("pos_x", 0)) or 0)
        y = float(snap.get("y", snap.get("pos_y", 0)) or 0)
        z = float(snap.get("z", snap.get("pos_z", 0)) or 0)
        cell = int(snap.get("cell", 0) or 0)
        loc_id = str(meta.get("location_id", "")).strip()
        entities.append(
            _npc_entity_row(
                pilot_id=pilot_id,
                name=name,
                x=x,
                y=y,
                z=z,
                cell=cell,
                location_id=loc_id,
                anchors=anchors,
            )
        )
        eid += 1
    # Pilotes catalogue sans snapshot (position poste)
    for pilot_id, meta in pilots.items():
        if pilot_id in seen:
            continue
        if not allow_roster_npc(pilot_id, meta, policies, roster_active):
            continue
        binding = meta.get("binding") or {}
        post = binding.get("post") or binding.get("home") or {}
        if not post:
            continue
        loc_id = str(meta.get("location_id", "")).strip()
        cell = int(post.get("cell", 0) or 0)
        entities.append(
            _npc_entity_row(
                pilot_id=pilot_id,
                name=str(meta.get("display_name", pilot_id)),
                x=float(post.get("x", 0) or 0),
                y=float(post.get("y", 0) or 0),
                z=float(post.get("z", 0) or 0),
                cell=cell,
                location_id=loc_id,
                anchors=anchors,
            )
        )
        eid += 1
    return entities


class Session:
    def __init__(self) -> None:
        self.logged_in = False
        self.character_id = 0
        self.in_world = False
        self.player_pos = _default_player_spawn()
        self.tick = 0


async def _send(ws: Any, payload: dict[str, Any]) -> None:
    payload.setdefault("proto", "lbg-ws/1")
    await ws.send(json.dumps(payload, ensure_ascii=False))


def _resolve_world_npc_id(target_id: str, pilots: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """target_id client → (world_npc_id, display_name)."""
    tid = (target_id or "").strip()
    if not tid:
        return "", ""
    if tid.startswith("npc:"):
        meta = pilots.get(tid, {})
        return tid, str(meta.get("display_name", tid))
    if tid.isdigit():
        # Ancien client : id numérique — introuvable sans table ; laisser tel quel
        return tid, tid
    return tid, tid


async def _handle_interact(
    ws: Any,
    sess: Session,
    data: dict[str, Any],
    pilots: dict[str, dict[str, Any]],
) -> None:
    msg = str(data.get("message", "")).strip()
    target = str(data.get("target_id", "")).strip()
    world_npc_id, npc_name = _resolve_world_npc_id(target, pilots)
    if not msg:
        await _send(ws, {"type": "error", "message": "message vide"})
        return
    if not world_npc_id:
        await _send(ws, {"type": "error", "message": "cible PNJ invalide"})
        return

    actor_id = f"player:prime:{sess.character_id or 1}"
    if PLACEHOLDER_ENABLED and ia_configured():
        await _send(
            ws,
            {
                "type": "chat",
                "from": npc_name or world_npc_id,
                "channel": "say",
                "message": placeholder_reply(npc_name),
                "trace_id": "prime-ph",
            },
        )

    ia_ctx = build_dialogue_context(
        world_npc_id,
        catalog_path=CATALOG,
        npc_name=npc_name or None,
    )
    reply, trace_id = await fetch_npc_reply(
        actor_id=actor_id,
        text=msg,
        world_npc_id=world_npc_id,
        npc_name=npc_name or None,
        ia_context=ia_ctx,
    )
    await _send(
        ws,
        {
            "type": "chat",
            "from": npc_name or world_npc_id,
            "channel": "say",
            "message": reply,
            "trace_id": trace_id,
        },
    )


async def _broadcast_loop(clients: set[Any]) -> None:
    while True:
        await asyncio.sleep(TICK_S)
        for ws in list(clients):
            sess: Session | None = getattr(ws, "lbg_sess", None)
            if sess is None or not sess.in_world:
                continue
            sess.tick += 1
            try:
                await _send(
                    ws,
                    {
                        "type": "world_state",
                        "tick": sess.tick,
                        "entities": _build_entities(sess.player_pos),
                    },
                )
            except ConnectionClosedOK:
                clients.discard(ws)
            except Exception:
                LOG.exception("broadcast failed")


async def _handler(ws: Any) -> None:
    clients: set[Any] = getattr(ws, "lbg_clients_ref", set())
    clients.add(ws)
    sess = Session()
    ws.lbg_sess = sess
    pilots = _catalog_pilots()
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "message": "JSON invalide"})
                continue
            if not isinstance(data, dict):
                continue
            t = data.get("type")
            if t == "login":
                sess.logged_in = True
                await _send(ws, {"type": "login_result", "success": True, "reason": None})
            elif t == "get_characters" and sess.logged_in:
                await _send(
                    ws,
                    {
                        "type": "characters_list",
                        "characters": [
                            {"id": 1, "name": "Teome", "race": "Wookiee", "profession": "entertainer"}
                        ],
                    },
                )
            elif t == "select_character" and sess.logged_in:
                sess.character_id = int(data.get("character_id", 1))
                sess.in_world = True
                await _send(
                    ws,
                    {
                        "type": "enter_world",
                        "map": "tatooine",
                        "zone": "tatooine",
                        "position": sess.player_pos,
                        "entities": _build_entities(sess.player_pos),
                    },
                )
            elif t == "enter_world" and sess.logged_in:
                sess.in_world = True
                await _send(
                    ws,
                    {
                        "type": "enter_world",
                        "map": "tatooine",
                        "zone": "tatooine",
                        "position": sess.player_pos,
                        "entities": _build_entities(sess.player_pos),
                    },
                )
            elif t == "move" and sess.in_world:
                pos = data.get("pos")
                if isinstance(pos, list) and len(pos) >= 3:
                    sess.player_pos = [float(pos[0]), float(pos[1]), float(pos[2])]
                    _maybe_inject_move(sess.player_pos)
                else:
                    d = data.get("direction") or [0, 0]
                    dt = float(data.get("dt", 0.1))
                    sess.player_pos[0] += float(d[0]) * 6.0 * dt
                    sess.player_pos[2] += float(d[1]) * 6.0 * dt
                    _maybe_inject_move(sess.player_pos)
            elif t == "interact" and sess.in_world:
                await _handle_interact(ws, sess, data, pilots)
            else:
                await _send(ws, {"type": "error", "message": f"type inconnu ou session: {t}"})
    finally:
        clients.discard(ws)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    clients: set[Any] = set()

    async def handler(ws: Any) -> None:
        ws.lbg_clients_ref = clients
        await _handler(ws)

    async with serve(handler, HOST, PORT):
        LOG.info(
            "lbg_gateway lbg-ws/1 on ws://%s:%s snapshots=%s ia=%s",
            HOST,
            PORT,
            SNAPSHOTS,
            "on" if ia_configured() else "off",
        )
        asyncio.create_task(_broadcast_loop(clients))
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_main())
