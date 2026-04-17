"""Test d'intégration : serveur réel + client WebSocket (port local)."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import socket
import unittest

from websockets.asyncio.client import connect


def _pick_listen_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _run_integration(port: int) -> None:
    stop = asyncio.Event()
    ready = asyncio.Event()
    # Ces tests doivent rester hermétiques : un poste de dev peut exporter des URLs LAN
    # qui activent le pont IA et cassent les assertions "pont désactivé".
    env_keys = (
        "MMMORPG_IA_BACKEND_URL",
        "MMMORPG_IA_BACKEND_PATH",
        "MMMORPG_IA_BACKEND_TOKEN",
        "MMMORPG_IA_PLACEHOLDER_ENABLED",
        "MMMORPG_IA_PLACEHOLDER_REPLY",
        "MMMORPG_IA_PLACEHOLDER_TRACE_ID",
        "MMMORPG_IA_TIMEOUT_S",
        "MMMORPG_DISABLE_PERSIST",
        "MMMORPG_STATE_PATH",
    )
    saved_env: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    os.environ["MMMORPG_DISABLE_PERSIST"] = "1"
    os.environ["MMMORPG_IA_PLACEHOLDER_ENABLED"] = "0"

    import mmmorpg_server.config as mm_cfg
    import mmmorpg_server.main as mm_main

    importlib.reload(mm_cfg)
    importlib.reload(mm_main)

    server_task = asyncio.create_task(
        mm_main.run_server(
            stop_event=stop,
            register_signals=False,
            host="127.0.0.1",
            port=port,
            ready_event=ready,
            configure_logging=False,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5.0)
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as ws:
            # Champs optionnels "pont jeu → IA" : sans backend configuré dans ce test,
            # le serveur doit rester compatible et ignorer ces champs.
            await ws.send(
                json.dumps(
                    {
                        "type": "hello",
                        "player_name": "integration",
                        "world_npc_id": "npc:innkeeper",
                        "npc_name": "Mara l’aubergiste",
                        "text": "Une chambre, s'il vous plaît.",
                    }
                )
            )
            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            welcome = json.loads(raw)
            assert welcome["type"] == "welcome"
            assert welcome.get("planet_id") == "terre1"
            assert "npc_reply" not in welcome  # pont désactivé sans MMMORPG_IA_BACKEND_URL
            pid = welcome["player_id"]
            assert isinstance(pid, str) and len(pid) > 0
            assert any(e.get("id") == pid for e in welcome.get("entities", []))

            await ws.send(
                json.dumps(
                    {
                        "type": "move",
                        "x": 25.0,
                        "y": 0.0,
                        "z": 10.0,
                        # Champs optionnels pont IA : sans MMMORPG_IA_BACKEND_URL, le serveur doit ignorer.
                        "world_npc_id": "npc:innkeeper",
                        "npc_name": "Mara l’aubergiste",
                        "text": "Et pour le souper ?",
                    }
                )
            )
            # Après move, on reçoit typiquement un world_tick (broadcast).
            for _ in range(5):
                raw2 = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg2 = json.loads(raw2)
                assert msg2["type"] in ("world_tick", "error")
                if msg2["type"] == "world_tick":
                    assert "npc_reply" not in msg2
                    break

        stop.set()
        await asyncio.wait_for(server_task, timeout=5.0)
    finally:
        for k, old in saved_env.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
        if not server_task.done():
            stop.set()
            try:
                await asyncio.wait_for(server_task, timeout=5.0)
            except asyncio.TimeoutError:
                server_task.cancel()
                try:
                    await server_task
                except asyncio.CancelledError:
                    pass


class TestWsIntegration(unittest.TestCase):
    def test_hello_move_lifecycle(self) -> None:
        port = _pick_listen_port()
        asyncio.run(_run_integration(port))


if __name__ == "__main__":
    unittest.main()
