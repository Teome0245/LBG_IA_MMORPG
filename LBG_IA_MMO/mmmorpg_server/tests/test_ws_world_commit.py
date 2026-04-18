"""WS move + world_commit (sans LLM) → snapshot interne."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import socket
import urllib.parse
import urllib.request

from websockets.asyncio.client import connect


def _pick_listen_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _snap_rep(base: str, npc_id: str, trace: str) -> int:
    path = f"/internal/v1/npc/{urllib.parse.quote(npc_id, safe=':')}/lyra-snapshot"
    url = f"{base}{path}?trace_id={urllib.parse.quote(trace)}"
    with urllib.request.urlopen(url, timeout=5) as r:
        j = json.loads(r.read().decode("utf-8"))
    ly = j["lyra"]
    return int(ly["meta"]["reputation"]["value"])


async def _run_case(*, ws_port: int, http_port: int, expect_conflict_error: bool) -> None:
    stop = asyncio.Event()
    ready = asyncio.Event()
    env_keys = (
        "MMMORPG_IA_BACKEND_URL",
        "MMMORPG_IA_BACKEND_PATH",
        "MMMORPG_IA_BACKEND_TOKEN",
        "MMMORPG_IA_PLACEHOLDER_ENABLED",
        "MMMORPG_IA_PLACEHOLDER_REPLY",
        "MMMORPG_IA_TIMEOUT_S",
        "MMMORPG_DISABLE_PERSIST",
        "MMMORPG_STATE_PATH",
        "MMMORPG_INTERNAL_HTTP_HOST",
        "MMMORPG_INTERNAL_HTTP_PORT",
        "MMMORPG_INTERNAL_HTTP_TOKEN",
    )
    saved_env: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    os.environ["MMMORPG_DISABLE_PERSIST"] = "1"
    os.environ["MMMORPG_INTERNAL_HTTP_HOST"] = "127.0.0.1"
    os.environ["MMMORPG_INTERNAL_HTTP_PORT"] = str(http_port)

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
        internal = f"http://127.0.0.1:{http_port}"
        uri = f"ws://127.0.0.1:{ws_port}"

        if expect_conflict_error:
            async with connect(uri) as ws:
                await ws.send(json.dumps({"type": "hello", "player_name": "t_world_commit_conflict"}))
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                assert json.loads(raw)["type"] == "welcome"
                await ws.send(
                    json.dumps(
                        {
                            "type": "move",
                            "x": 1.0,
                            "y": 0.0,
                            "z": 0.0,
                            "world_npc_id": "npc:merchant",
                            "text": "Bonjour",
                            "world_commit": {
                                "npc_id": "npc:merchant",
                                "trace_id": "conflict-1",
                                "flags": {"reputation_delta": 1},
                            },
                        }
                    )
                )
                raw_e = await asyncio.wait_for(ws.recv(), timeout=3.0)
                err = json.loads(raw_e)
                assert err["type"] == "error"
                assert "incompatible" in (err.get("message") or "")
        else:
            async with connect(uri) as ws:
                await ws.send(json.dumps({"type": "hello", "player_name": "t_world_commit"}))
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                assert json.loads(raw)["type"] == "welcome"

                tid = "ws-commit-test-1"
                before = _snap_rep(internal, "npc:merchant", "t0")
                await ws.send(
                    json.dumps(
                        {
                            "type": "move",
                            "x": 5.0,
                            "y": 0.0,
                            "z": 1.0,
                            "world_commit": {
                                "npc_id": "npc:merchant",
                                "trace_id": tid,
                                "flags": {"reputation_delta": 4},
                            },
                        }
                    )
                )
                for _ in range(8):
                    raw2 = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    m2 = json.loads(raw2)
                    if m2["type"] == "world_tick":
                        break
                    assert m2["type"] != "error", m2
                after = _snap_rep(internal, "npc:merchant", "t1")
                lo = max(-100, min(100, before + 4))
                assert after == lo

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


def test_ws_move_world_commit_updates_snapshot() -> None:
    ws_p = _pick_listen_port()
    http_p = _pick_listen_port()
    asyncio.run(_run_case(ws_port=ws_p, http_port=http_p, expect_conflict_error=False))


def test_ws_move_world_commit_rejects_ia_combo() -> None:
    ws_p = _pick_listen_port()
    http_p = _pick_listen_port()
    asyncio.run(_run_case(ws_port=ws_p, http_port=http_p, expect_conflict_error=True))


def test_parse_move_world_commit_errors() -> None:
    from mmmorpg_server.main import _parse_move_world_commit

    assert _parse_move_world_commit({}) is None
    assert isinstance(_parse_move_world_commit({"world_commit": "x"}), str)
    assert isinstance(_parse_move_world_commit({"world_commit": {}}), str)
    ok = _parse_move_world_commit(
        {"world_commit": {"npc_id": "npc:merchant", "trace_id": "abc", "flags": {"reputation_delta": 2}}}
    )
    assert isinstance(ok, dict)
    assert ok["npc_id"] == "npc:merchant" and ok["trace_id"] == "abc"
