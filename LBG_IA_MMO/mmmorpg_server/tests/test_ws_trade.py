"""WS trade v1 : buy/sell + funds + world_event."""

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
        "MMMORPG_TRADE_MAX_DISTANCE_M",
    )
    saved_env: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    os.environ["MMMORPG_DISABLE_PERSIST"] = "1"
    os.environ["MMMORPG_MOVE_MIN_INTERVAL_S"] = "0"
    os.environ["MMMORPG_TRADE_MAX_DISTANCE_M"] = "999"

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
            await ws.send(json.dumps({"type": "hello", "player_name": "t_trade"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            w = json.loads(raw)
            assert w["type"] == "welcome"

            # Buy 1 rations from merchant (cost 3 bronze).
            await ws.send(
                json.dumps(
                    {
                        "type": "trade",
                        "npc_id": "npc:merchant",
                        "side": "buy",
                        "item_id": "item:rations",
                        "qty": 1,
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "trace_id": "t1",
                    }
                )
            )
            got = False
            for _ in range(20):
                raw2 = await asyncio.wait_for(ws.recv(), timeout=3.0)
                m2 = json.loads(raw2)
                if m2["type"] == "error":
                    raise AssertionError(m2.get("message"))
                if m2["type"] != "world_tick":
                    continue
                we = m2.get("world_event")
                if isinstance(we, dict) and we.get("type") == "trade":
                    assert we.get("status") == "bought"
                    assert we.get("npc_id") == "npc:merchant"
                    assert we.get("item_id") == "item:rations"
                    assert int(we.get("total") or 0) == 3
                    got = True
                    break
            assert got, "pas d'event trade reçu"
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


def test_ws_trade_emits_event() -> None:
    ws_p = _pick_listen_port()
    asyncio.run(_run_case(ws_port=ws_p))

