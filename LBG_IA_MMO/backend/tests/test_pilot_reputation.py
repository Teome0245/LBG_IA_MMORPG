from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeResp:
    status_code = 200

    def json(self) -> dict:
        return {"status": "ok", "accepted": True, "reason": "accepted"}

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
        if "/internal/v1/npc/npc:merchant/dialogue-commit" in url:
            assert json.get("trace_id")
            flags = json.get("flags")
            assert isinstance(flags, dict)
            assert flags.get("reputation_delta") == 11
        elif "/internal/v1/npc/npc:merchant/reputation" in url:
            assert json.get("delta") == 11
            # Si un token monde est configuré côté backend, il doit être relayé en header.
            expected = os.environ.get("LBG_MMO_INTERNAL_TOKEN", "").strip()
            if expected:
                assert isinstance(headers, dict)
                assert headers.get("X-LBG-Service-Token") == expected
        else:
            raise AssertionError(f"url inattendue: {url}")
        return _FakeResp()


def test_pilot_reputation_calls_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setenv("LBG_MMO_SERVER_URL", "http://127.0.0.1:8050")
    monkeypatch.setenv("LBG_MMO_INTERNAL_TOKEN", "mmo-secret")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    r = client.post("/v1/pilot/reputation", json={"npc_id": "npc:merchant", "delta": 11})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("commit_result", {}).get("ok") is True


def test_pilot_reputation_rejects_bad_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    from backend.main import app

    client = TestClient(app)
    assert client.post("/v1/pilot/reputation", json={}).status_code == 400
    assert client.post("/v1/pilot/reputation", json={"npc_id": "npc:merchant"}).status_code == 400
    assert client.post("/v1/pilot/reputation", json={"npc_id": "npc:merchant", "delta": 101}).status_code == 400


def test_pilot_reputation_requires_token_if_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PILOT_INTERNAL_TOKEN", "secret")
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    r1 = client.post("/v1/pilot/reputation", json={"npc_id": "npc:merchant", "delta": 11})
    assert r1.status_code == 401
    r2 = client.post(
        "/v1/pilot/reputation",
        headers={"X-LBG-Service-Token": "secret"},
        json={"npc_id": "npc:merchant", "delta": 11},
    )
    assert r2.status_code == 200

