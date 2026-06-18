import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    """Mock orchestrateur : journalise l'appel et renvoie une réponse de job factice."""

    last_call: dict[str, object] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict[str, object] | None = None) -> _FakeResponse:
        _FakeAsyncClient.last_call = {"method": "POST", "url": url, "json": json}
        return _FakeResponse({"id": "job-1", "status": "running", "objective": "x", "steps": [], "events": []})

    async def get(self, url: str, params: dict[str, object] | None = None) -> _FakeResponse:
        _FakeAsyncClient.last_call = {"method": "GET", "url": url, "params": params}
        return _FakeResponse({"jobs": [{"id": "job-1", "actor_id": "u", "objective": "x", "status": "done"}]})


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://fake:8010")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", _FakeAsyncClient)
    from backend.main import app

    return TestClient(app)


def test_pilot_jobs_create_proxy_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    r = client.post("/v1/pilot/jobs", json={"actor_id": "u", "objective": "vérifie le backend"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data["id"] == "job-1"
    assert _FakeAsyncClient.last_call["url"].endswith("/v1/jobs")


def test_pilot_jobs_list_proxy_filters_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    r = client.get("/v1/pilot/jobs", params={"actor_id": "u"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert _FakeAsyncClient.last_call["params"] == {"actor_id": "u"}


def test_pilot_jobs_approve_proxy_forwards_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    r = client.post("/v1/pilot/jobs/job-1/approve", json={"token": "ok-go"})
    assert r.status_code == 200
    assert _FakeAsyncClient.last_call["json"] == {"token": "ok-go"}
    assert _FakeAsyncClient.last_call["url"].endswith("/v1/jobs/job-1/approve")
