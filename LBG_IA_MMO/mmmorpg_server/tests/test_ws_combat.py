"""WS combat v1 (auto-attack) : start/stop + world_event hit."""

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
    )
    saved_env: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    os.environ["MMMORPG_DISABLE_PERSIST"] = "1"
    os.environ["MMMORPG_MOVE_MIN_INTERVAL_S"] = "0"
    os.environ["MMMORPG_COMBAT_TICK_S"] = "0.2"
    os.environ["MMMORPG_COMBAT_RANGE_M"] = "50"
    os.environ["MMMORPG_COMBAT_BASE_DAMAGE"] = "3"

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
            await ws.send(json.dumps({"type": "hello", "player_name": "t_combat"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            w = json.loads(raw)
            assert w["type"] == "welcome"
            pid = w["player_id"]

            # Démarrer le combat sur un PNJ stable du seed de fallback.
            await ws.send(json.dumps({"type": "combat", "action": "start", "target_id": "npc:merchant"}))

            found_hit = False
            for _ in range(40):
                raw2 = await asyncio.wait_for(ws.recv(), timeout=3.0)
                m2 = json.loads(raw2)
                if m2["type"] == "error":
                    raise AssertionError(m2.get("message"))
                if m2["type"] != "world_tick":
                    continue
                we = m2.get("world_event")
                if isinstance(we, dict) and we.get("type") == "combat_hit":
                    assert we.get("source_id") == pid
                    assert we.get("target_id") == "npc:merchant"
                    assert int(we.get("amount") or 0) == 3
                    found_hit = True
                    break
            assert found_hit, "aucun combat_hit reçu"
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


def test_ws_combat_emits_hit_event() -> None:
    ws_p = _pick_listen_port()
    asyncio.run(_run_case(ws_port=ws_p))

