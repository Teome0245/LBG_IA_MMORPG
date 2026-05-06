import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> dict[str, object]:
        return {
            "actor_id": "ui:assistant",
            "proposal": {
                "capability": "desktop_control",
                "routed_to": "agent.desktop",
                "action_context_key": "desktop_action",
                "action": {"kind": "search_web_open", "query": "Cursor AI"},
                "context_patch": {"desktop_action": {"kind": "search_web_open", "query": "Cursor AI"}, "desktop_dry_run": True},
                "summary": "Préparer une recherche web.",
                "risk_level": "high",
                "requires_review": True,
                "confidence": 0.8,
                "source": "deterministic",
            },
            "reason": None,
        }


class _FakeAsyncClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.last_json: dict[str, object] | None = None

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]) -> _FakeResponse:
        self.last_json = json
        assert url == "http://fake:8010/v1/action-proposal"
        assert json["text"] == "cherche sur internet le site de Cursor AI"
        return _FakeResponse()


def test_pilot_action_proposal_proxy_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://fake:8010")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", _FakeAsyncClient)

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/action-proposal",
        json={"actor_id": "ui:assistant", "text": "cherche sur internet le site de Cursor AI", "context": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["proposal"]["capability"] == "desktop_control"
    assert data["proposal"]["action"]["kind"] == "search_web_open"
