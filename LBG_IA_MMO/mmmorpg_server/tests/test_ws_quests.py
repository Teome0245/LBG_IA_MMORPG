"""WS quests v1 : accept + kill progression + turnin reward ; deliver turnin."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import socket

from websockets.asyncio.client import connect


def _pick_listen_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _run_case(*, ws_port: int) -> None:
    stop = asyncio.Event()
    ready = asyncio.Event()
    env_keys = (
        "MMMORPG_DISABLE_PERSIST",
        "MMMORPG_STATE_PATH",
        "MMMORPG_IA_BACKEND_URL",
        "MMMORPG_MOVE_MIN_INTERVAL_S",
        "MMMORPG_COMBAT_TICK_S",
        "MMMORPG_COMBAT_RANGE_M",
        "MMMORPG_COMBAT_BASE_DAMAGE",
        "MMMORPG_TRADE_MAX_DISTANCE_M",
    )
    saved_env: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    os.environ["MMMORPG_DISABLE_PERSIST"] = "1"
    os.environ["MMMORPG_MOVE_MIN_INTERVAL_S"] = "0"
    os.environ["MMMORPG_TRADE_MAX_DISTANCE_M"] = "999"
    os.environ["MMMORPG_COMBAT_TICK_S"] = "0.15"
    os.environ["MMMORPG_COMBAT_RANGE_M"] = "999"
    os.environ["MMMORPG_COMBAT_BASE_DAMAGE"] = "50"

    import mmmorpg_server.config as mm_cfg
    import mmmorpg_server.main as mm_main

    importlib.reload(mm_cfg)
    importlib.reload(mm_main)

    server_task = asyncio.create_task(
        mm_main.run_server(
            stop_event=stop,
            register_signals=False,
            host="127.0.0.1",
            port=ws_port,
            ready_event=ready,
            configure_logging=False,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5.0)
        uri = f"ws://127.0.0.1:{ws_port}"
        async with connect(uri) as ws:
            await ws.send(json.dumps({"type": "hello", "player_name": "t_quests"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            w = json.loads(raw)
            assert w["type"] == "welcome"

            # Accept kill quest (boars).
            await ws.send(json.dumps({"type": "quest", "action": "accept", "quest_id": "quest:boars", "npc_id": "npc:guard", "x": 0, "y": 0, "z": 0}))
            got_accept = False
            for _ in range(30):
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                if m.get("type") != "world_tick":
                    continue
                ev = m.get("world_event")
                if isinstance(ev, dict) and ev.get("type") == "quest_update" and ev.get("status") == "accepted":
                    got_accept = True
                    break
            assert got_accept

            # Kill two boars quickly via auto-attack.
            for tid in ("npc:boar_1", "npc:boar_2"):
                await ws.send(json.dumps({"type": "combat", "action": "start", "target_id": tid}))
                got_kill = False
                for _ in range(40):
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                    if m.get("type") != "world_tick":
                        continue
                    ev = m.get("world_event")
                    if isinstance(ev, dict) and ev.get("type") == "combat_kill" and ev.get("target_id") == tid:
                        got_kill = True
                        break
                assert got_kill

            # Turn in should complete.
            await ws.send(json.dumps({"type": "quest", "action": "turnin", "npc_id": "npc:guard", "x": 0, "y": 0, "z": 0}))
            got_comp = False
            for _ in range(40):
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                if m.get("type") != "world_tick":
                    continue
                ev = m.get("world_event")
                if isinstance(ev, dict) and ev.get("type") == "quest_complete" and ev.get("quest_id") == "quest:boars":
                    got_comp = True
                    break
            assert got_comp

            # Deliver quest: gather 3 brindilles then turn in at merchant.
            await ws.send(json.dumps({"type": "quest", "action": "accept", "quest_id": "quest:brindilles", "npc_id": "npc:merchant", "x": 0, "y": 0, "z": 0}))
            # gather x3
            for _ in range(3):
                await ws.send(json.dumps({"type": "job", "action": "gather", "kind": "brindille"}))
            await ws.send(json.dumps({"type": "quest", "action": "turnin", "npc_id": "npc:merchant", "x": 0, "y": 0, "z": 0}))
            got_comp2 = False
            for _ in range(60):
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                if m.get("type") != "world_tick":
                    continue
                ev = m.get("world_event")
                if isinstance(ev, dict) and ev.get("type") == "quest_complete" and ev.get("quest_id") == "quest:brindilles":
                    got_comp2 = True
                    break
            assert got_comp2
    finally:
        stop.set()
        try:
            await asyncio.wait_for(server_task, timeout=5.0)
        except asyncio.TimeoutError:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        for k, old in saved_env.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def test_ws_quests_kill_and_deliver() -> None:
    ws_p = _pick_listen_port()
    asyncio.run(_run_case(ws_port=ws_p))

