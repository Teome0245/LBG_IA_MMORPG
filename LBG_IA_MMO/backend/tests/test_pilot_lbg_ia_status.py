import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


def test_pilot_lbg_ia_status_disabled_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_LBGIA_BACKEND_URL", raising=False)
    monkeypatch.delenv("LBG_IA_BACKEND_URL", raising=False)
    from main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/lbg-ia/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is False
    assert data.get("disabled") is True


def test_pilot_lbg_ia_status_ok_with_mocked_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PILOT_LBGIA_BACKEND_URL", "http://lbg-ia-fake")

    class _FakeResp:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = ""

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _FakeResp:
            if url.endswith("/metrics"):
                return _FakeResp(200, {"system": {"cpu_usage_pct": 12.0, "memory_usage_pct": 45.0}})
            if "/monitor/agents" in url:
                return _FakeResp(200, {"agents": []})
            return _FakeResp(404, {})

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    from main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/lbg-ia/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("upstream_base") == "http://lbg-ia-fake"
    assert isinstance(data.get("metrics"), dict)
    assert isinstance(data.get("agents_monitor"), dict)
