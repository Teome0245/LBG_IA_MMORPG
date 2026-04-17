import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> dict[str, object]:
        return {"capabilities": [{"name": "x", "routed_to": "agent.x", "description": ""}]}


class _FakeAsyncClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse()


def test_pilot_capabilities_proxy_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://fake:8010")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", _FakeAsyncClient)

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert len(data["capabilities"]) == 1
