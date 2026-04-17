"""
Chaîne phase C : POST /v1/pilot/route applique merge_mmo_lyra avant l'orchestrateur
(world_npc_id + LBG_MMO_SERVER_URL), sans services réseau (httpx mocké).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod
from models.intents import IntentResponse


class _FakeResp:
    status_code = 200

    def json(self) -> dict:
        return {
            "npc_id": "npc:smith",
            "lyra": {
                "version": "lyra-context-1",
                "gauges": {"hunger": 0.33, "thirst": 0.0, "fatigue": 0.0},
                "meta": {"source": "mmo_world", "npc_id": "npc:smith"},
            },
        }


class _FakeAsyncClient:
    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str, params: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
        # Dans ce test on valide le chemin historique mmo_server (pas le snapshot WS).
        assert "/v1/world/lyra" in url
        assert params == {"npc_id": "npc:smith"}
        assert headers is None
        return _FakeResp()


def _fake_async_client(*args: object, **kwargs: object) -> _FakeAsyncClient:
    return _FakeAsyncClient()


class _CaptureOrch:
    last_payload: object | None = None

    async def route_intent(self, payload: object) -> IntentResponse:
        _CaptureOrch.last_payload = payload
        return IntentResponse(
            intent="npc_dialogue",
            confidence=0.9,
            routed_to="agent.dialogue",
            output={"reply": "ok"},
        )


def test_pilot_route_injects_mmo_lyra_before_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _CaptureOrch())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={
            "actor_id": "p:1",
            "text": "Bonjour forgeron",
            "context": {"world_npc_id": "npc:smith"},
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    payload = _CaptureOrch.last_payload
    assert payload is not None
    ctx = getattr(payload, "context", None)
    assert isinstance(ctx, dict)
    ly = ctx.get("lyra")
    assert isinstance(ly, dict)
    assert ly.get("meta", {}).get("source") == "mmo_world"
    assert ly.get("gauges", {}).get("hunger") == 0.33
