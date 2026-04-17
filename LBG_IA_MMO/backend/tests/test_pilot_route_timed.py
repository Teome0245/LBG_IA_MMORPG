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
            output={"reply": "Salut."},
        )


def test_pilot_route_returns_elapsed_ms_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrchClient())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={"actor_id": "test:1", "text": "Bonjour", "context": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert isinstance(data.get("trace_id"), str)
    assert len(data["trace_id"]) >= 16
    assert isinstance(data.get("elapsed_ms"), int)
    assert data["elapsed_ms"] >= 0
    res = data.get("result")
    assert isinstance(res, dict)
    assert res.get("routed_to") == "agent.dialogue"

