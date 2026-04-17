import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeOk:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {"status": "ok", "service": "combat_http", "version": "0.2.0"}


class _FakeClient:
    def __init__(self, *a: object, **k: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def get(self, url: str) -> _FakeOk:
        assert "/healthz" in url
        return _FakeOk()


def test_pilot_status_includes_combat_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_COMBAT_URL", "http://127.0.0.1:8040")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/status")
    assert r.status_code == 200
    data = r.json()
    assert data["agent_combat"] == "ok"
    assert data["agent_combat_url"] == "http://127.0.0.1:8040"
    info = data.get("agent_combat_info")
    assert isinstance(info, dict)
    assert info.get("service") == "combat_http"
