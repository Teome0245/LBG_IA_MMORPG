from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod
from backend.main import create_app
from models.intents import IntentResponse


class _FakeOrchClient:
    async def route_intent(self, payload: object) -> IntentResponse:
        return IntentResponse(
            intent="npc_dialogue",
            confidence=0.9,
            routed_to="agent.dialogue",
            output={"reply": "Salut."},
        )


def test_metrics_disabled_by_default() -> None:
    os.environ.pop("LBG_METRICS_ENABLED", None)
    os.environ.pop("LBG_METRICS_TOKEN", None)
    client = TestClient(create_app())
    r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_enabled_counts_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_METRICS_ENABLED", "1")
    monkeypatch.delenv("LBG_METRICS_TOKEN", raising=False)
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrchClient())

    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
    r_route = client.post(
        "/v1/pilot/route",
        json={"actor_id": "test:metrics", "text": "Bonjour", "context": {}},
    )
    assert r_route.status_code == 200
    assert r_route.json().get("ok") is True

    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "lbg_process_uptime_seconds" in body
    assert "pilot_route_requests_total" in body or "pilot_route_success_total" in body
