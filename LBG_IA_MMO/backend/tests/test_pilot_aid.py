from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeResp:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    @property
    def text(self) -> str:
        return "ok"


class _FakeAsyncClient:
    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str, json: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
        assert isinstance(url, str)
        assert isinstance(json, dict)
        assert "/internal/v1/npc/npc:merchant/aid" in url
        assert isinstance(json.get("trace_id"), str) and json["trace_id"]
        assert json.get("hunger_delta") == -0.2
        assert json.get("thirst_delta") == -0.1
        assert json.get("fatigue_delta") == 0.0
        assert json.get("reputation_delta") == 5

        expected = os.environ.get("LBG_MMO_INTERNAL_TOKEN", "").strip()
        if expected:
            assert isinstance(headers, dict)
            assert headers.get("X-LBG-Service-Token") == expected
        else:
            assert headers is None

        return _FakeResp({"ok": True, "npc_id": "npc:merchant", "lyra": {"meta": {"source": "mmo_world"}}})

    async def get(self, url: str, params: object | None = None) -> _FakeResp:  # type: ignore[override]
        assert "/v1/world/lyra" in url
        assert params == {"npc_id": "npc:merchant"}
        return _FakeResp({"npc_id": "npc:merchant", "lyra": {"meta": {"source": "mmo_world"}}})


def test_pilot_aid_calls_mmo_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setenv("LBG_MMO_INTERNAL_TOKEN", "mmo-secret")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/aid",
        json={"npc_id": "npc:merchant", "hunger_delta": -0.2, "thirst_delta": -0.1, "reputation_delta": 5},
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("world_result", {}).get("ok") is True


def test_pilot_proxy_world_lyra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/mmo-server/world-lyra", params={"npc_id": "npc:merchant"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("npc_id") == "npc:merchant"


def test_pilot_aid_requires_token_if_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PILOT_INTERNAL_TOKEN", "secret")
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    r1 = client.post("/v1/pilot/aid", json={"npc_id": "npc:merchant"})
    assert r1.status_code == 401
    r2 = client.post(
        "/v1/pilot/aid",
        headers={"X-LBG-Service-Token": "secret"},
        json={"npc_id": "npc:merchant", "hunger_delta": -0.2, "thirst_delta": -0.1, "reputation_delta": 5},
    )
    assert r2.status_code == 200

