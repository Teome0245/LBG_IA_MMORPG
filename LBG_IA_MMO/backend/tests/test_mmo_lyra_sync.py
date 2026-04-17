import asyncio

import pytest

import httpx

from services.mmo_lyra_sync import merge_mmo_lyra_if_configured


class _FakeResp:
    status_code = 200

    def json(self) -> dict:
        return {
            "lyra": {
                "version": "lyra-context-1",
                "gauges": {"hunger": 0.11, "thirst": 0.0, "fatigue": 0.0},
                "meta": {"source": "mmo_world", "npc_id": "npc:smith"},
            }
        }


class _FakeClient:
    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str, params: object | None = None) -> _FakeResp:
        return _FakeResp()


def _fake_async_client(*args: object, **kwargs: object) -> _FakeClient:
    return _FakeClient()


def test_merge_injects_lyra_when_url_and_npc_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)
    ctx: dict = {"world_npc_id": "npc:smith"}

    async def _run() -> None:
        await merge_mmo_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert ctx["lyra"]["meta"]["source"] == "mmo_world"
    assert ctx["lyra"]["gauges"]["hunger"] == 0.11


def test_merge_prefers_mmmorpg_internal_snapshot_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResp2:
        status_code = 200

        def json(self) -> dict:
            return {
                "status": "ok",
                "lyra": {
                    "version": "lyra-context-2",
                    "kind": "npc_world",
                    "gauges": {"hunger": 0.9, "thirst": 0.1, "fatigue": 0.2},
                    "meta": {"source": "mmmorpg_ws", "npc_id": "npc:smith"},
                },
            }

    class _FakeClient2:
        async def __aenter__(self) -> "_FakeClient2":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(self, url: str, params: object | None = None, headers: object | None = None) -> _FakeResp2:  # type: ignore[override]
            assert "/internal/v1/npc/npc:smith/lyra-snapshot" in url
            assert params == {"trace_id": "t1"}
            assert headers == {"X-LBG-Service-Token": "tok"}
            return _FakeResp2()

    def _fake_async_client2(*args: object, **kwargs: object) -> _FakeClient2:
        return _FakeClient2()

    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", "tok")
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")  # fallback présent mais ne doit pas être utilisé
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client2)
    ctx: dict = {"world_npc_id": "npc:smith", "_trace_id": "t1"}

    async def _run() -> None:
        await merge_mmo_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert ctx["lyra"]["meta"]["source"] == "mmmorpg_ws"
    assert ctx["lyra"]["gauges"]["hunger"] == 0.9


def test_merge_noop_without_world_npc_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)
    ctx: dict = {"npc_name": "X"}

    async def _run() -> None:
        await merge_mmo_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert "lyra" not in ctx


def test_merge_respects_skip_mmo_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)
    ctx: dict = {
        "world_npc_id": "npc:smith",
        "lyra": {"meta": {"skip_mmo_sync": True}, "gauges": {"stress": 1}},
    }

    async def _run() -> None:
        await merge_mmo_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert ctx["lyra"]["gauges"]["stress"] == 1


def test_merge_fallbacks_to_mmo_server_when_mmmorpg_snapshot_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _RespFail:
        status_code = 401

        def json(self) -> dict:
            return {"error": "unauthorized"}

        @property
        def text(self) -> str:
            return "unauthorized"

    class _RespOk:
        status_code = 200

        def json(self) -> dict:
            return {
                "lyra": {
                    "version": "lyra-context-1",
                    "gauges": {"hunger": 0.22, "thirst": 0.0, "fatigue": 0.0},
                    "meta": {"source": "mmo_world", "npc_id": "npc:smith"},
                }
            }

        @property
        def text(self) -> str:
            return "ok"

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(self, url: str, params: object | None = None, headers: object | None = None):  # type: ignore[override]
            calls.append(url)
            if "/internal/v1/npc/" in url and "/lyra-snapshot" in url:
                return _RespFail()
            if "/v1/world/lyra" in url:
                assert params == {"npc_id": "npc:smith"}
                return _RespOk()
            raise AssertionError(f"url inattendue: {url}")

    def _client(*args: object, **kwargs: object) -> _Client:
        return _Client()

    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(httpx, "AsyncClient", _client)

    ctx: dict = {"world_npc_id": "npc:smith", "_trace_id": "t1"}

    async def _run() -> None:
        await merge_mmo_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert ctx["lyra"]["meta"]["source"] == "mmo_world"
    assert any("/internal/v1/npc/" in u for u in calls)
    assert any("/v1/world/lyra" in u for u in calls)
