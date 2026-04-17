"""
E2E léger (phase C) : pilot → orchestrateur (mock) avec intention DevOps ;
vérifie que ``trace_id`` est bien injecté dans ``context._trace_id`` avant routage.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod
from models.intents import IntentResponse


class _FakeOrch:
    last_payload: object | None = None

    async def route_intent(self, payload: object) -> IntentResponse:
        _FakeOrch.last_payload = payload
        return IntentResponse(
            intent="devops_probe",
            confidence=1.0,
            routed_to="agent.devops",
            output={"agent": "devops_executor", "capability": "devops_probe"},
        )


def test_pilot_route_devops_carries_trace_id_to_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeOrch.last_payload = None
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrch())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={
            "actor_id": "ops:1",
            "text": "sonde devops",
            "context": {},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    tid = body.get("trace_id")
    assert isinstance(tid, str) and len(tid) >= 16

    payload = _FakeOrch.last_payload
    assert payload is not None
    ctx = getattr(payload, "context", None)
    assert isinstance(ctx, dict)
    assert ctx.get("_trace_id") == tid


def test_pilot_route_keeps_preset_trace_in_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comportement actuel : ``setdefault`` conserve un ``_trace_id`` client ; le JSON de réponse expose tout de même un nouveau ``trace_id`` (UUID pilot)."""
    _FakeOrch.last_payload = None
    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _FakeOrch())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={
            "actor_id": "ops:1",
            "text": "hello",
            "context": {"_trace_id": "preset-trace-123"},
        },
    )
    assert r.status_code == 200
    body_tid = r.json().get("trace_id")
    payload = _FakeOrch.last_payload
    ctx = getattr(payload, "context", {})
    assert isinstance(ctx, dict)
    assert ctx.get("_trace_id") == "preset-trace-123"
    assert body_tid != "preset-trace-123"
