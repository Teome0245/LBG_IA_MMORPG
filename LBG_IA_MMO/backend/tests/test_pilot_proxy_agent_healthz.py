import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeOk:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {"status": "ok", "service": "dialogue_http"}


class _FakeClient:
    def __init__(self, *a: object, **k: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def get(self, url: str) -> _FakeOk:
        assert url.endswith("/healthz")
        return _FakeOk()


def test_pilot_proxy_dialogue_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DIALOGUE_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("skipped") is True


def test_pilot_proxy_dialogue_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "dialogue_http"


def test_pilot_proxy_quests_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-quests/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_combat_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_COMBAT_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-combat/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_combat_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_COMBAT_URL", "http://127.0.0.1:8040")

    class _OkCombat:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"status": "ok", "service": "combat_http", "version": "0.2.0"}

    class _ClientCombat:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientCombat":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _OkCombat:
            assert url.endswith("/healthz")
            return _OkCombat()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientCombat())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-combat/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "combat_http"
