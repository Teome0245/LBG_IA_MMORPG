import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod
from models.intents import IntentResponse


class _FakeOrchClient:
    async def route_intent(self, payload: object) -> IntentResponse:
        return IntentResponse(
            intent="npc_dialogue",
            confidence=0.9,
            routed_to="agent.dialogue",
            output={"reply": "OK"},
        )


def test_pilot_internal_requires_token_if_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrchClient())
    monkeypatch.setenv("LBG_PILOT_INTERNAL_TOKEN", "secret")

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/internal/route",
        json={"actor_id": "svc:mmmorpg", "text": "Bonjour", "context": {"world_npc_id": "npc:test"}},
    )
    assert r.status_code == 401

    r2 = client.post(
        "/v1/pilot/internal/route",
        headers={"X-LBG-Service-Token": "secret"},
        json={"actor_id": "svc:mmmorpg", "text": "Bonjour", "context": {"world_npc_id": "npc:test"}},
    )
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_pilot_internal_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrchClient())
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_PILOT_INTERNAL_RL_RPS", "0.0001")
    monkeypatch.setenv("LBG_PILOT_INTERNAL_RL_BURST", "1")

    from backend.main import app

    client = TestClient(app)
    body = {"actor_id": "svc:mmmorpg", "text": "Bonjour", "context": {"world_npc_id": "npc:test"}}

    r1 = client.post("/v1/pilot/internal/route", json=body)
    assert r1.status_code == 200
    r2 = client.post("/v1/pilot/internal/route", json=body)
    assert r2.status_code == 429

