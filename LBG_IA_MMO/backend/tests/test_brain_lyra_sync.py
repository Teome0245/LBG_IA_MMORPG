import asyncio

import httpx
import pytest

from services.brain_lyra_sync import merge_brain_lyra_if_configured


class _Resp:
    status_code = 200

    def json(self) -> dict:
        return {"gauges": {"stress": 80.0, "confidence": 30.0}}


class _Client:
    async def __aenter__(self) -> "_Client":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str) -> _Resp:  # type: ignore[override]
        assert url.endswith("/v1/brain/status")
        return _Resp()


def _client(*args: object, **kwargs: object) -> _Client:
    return _Client()


def test_brain_bridge_world_applies_small_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_BRAIN_LYRA_BRIDGE_ENABLED", "1")
    monkeypatch.setenv("LBG_BRAIN_LYRA_WORLD_SCALE", "0.03")
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(httpx, "AsyncClient", _client)
    ctx = {
        "lyra": {
            "kind": "npc_world",
            "gauges": {"hunger": 0.2, "thirst": 0.1, "fatigue": 0.3},
            "meta": {"source": "pilot_standalone"},
        }
    }

    async def _run() -> None:
        await merge_brain_lyra_if_configured(ctx)

    asyncio.run(_run())
    g = ctx["lyra"]["gauges"]
    assert g["hunger"] > 0.2
    assert g["thirst"] > 0.1
    assert g["fatigue"] > 0.3
    assert ctx["lyra"]["meta"]["brain_bridge"]["enabled"] is True


def test_brain_bridge_assistant_updates_gauges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_BRAIN_LYRA_BRIDGE_ENABLED", "1")
    monkeypatch.setenv("LBG_BRAIN_LYRA_ASSISTANT_SCALE", "5")
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(httpx, "AsyncClient", _client)
    ctx = {
        "lyra": {
            "kind": "assistant",
            "gauges": {"chaleur": 60.0, "energie": 70.0, "patience": 55.0, "confiance": 65.0},
            "meta": {"source": "pilot_assistant"},
        }
    }

    async def _run() -> None:
        await merge_brain_lyra_if_configured(ctx)

    asyncio.run(_run())
    g = ctx["lyra"]["gauges"]
    assert g["patience"] < 55.0
    assert g["energie"] < 70.0
    assert "brain_bridge" in ctx["lyra"]["meta"]


def test_brain_bridge_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_BRAIN_LYRA_BRIDGE_ENABLED", raising=False)
    ctx = {"lyra": {"kind": "npc_world", "gauges": {"hunger": 0.2}, "meta": {}}}

    async def _run() -> None:
        await merge_brain_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert ctx["lyra"]["gauges"]["hunger"] == 0.2
    assert "brain_bridge" not in ctx["lyra"]["meta"]

