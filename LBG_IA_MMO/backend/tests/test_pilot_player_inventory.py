from __future__ import annotations

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
        assert "/internal/v1/npc/npc:merchant/dialogue-commit" in url
        assert json.get("trace_id")
        assert json.get("player_id") == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        flags = json.get("flags")
        assert isinstance(flags, dict)
        assert flags.get("player_item_id") == "item:potion"
        assert flags.get("player_item_qty_delta") == 2
        assert flags.get("player_item_label") == "Potion"
        return _FakeResp()


def test_pilot_player_inventory_calls_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    r = client.post(
        "/v1/pilot/player-inventory",
        json={
            "npc_id": "npc:merchant",
            "player_id": pid,
            "item_id": "item:potion",
            "qty_delta": 2,
            "label": "Potion",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("commit_result", {}).get("ok") is True


def test_pilot_player_inventory_rejects_bad_qty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_PILOT_INTERNAL_TOKEN", raising=False)
    from backend.main import app

    client = TestClient(app)
    base = {
        "npc_id": "npc:merchant",
        "player_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "item_id": "item:x",
    }
    assert client.post("/v1/pilot/player-inventory", json={**base, "qty_delta": 0}).status_code == 400
    assert client.post("/v1/pilot/player-inventory", json={**base, "qty_delta": 99}).status_code == 400


def test_pilot_player_inventory_requires_token_if_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PILOT_INTERNAL_TOKEN", "secret")
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient())

    from backend.main import app

    client = TestClient(app)
    body = {
        "npc_id": "npc:merchant",
        "player_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "item_id": "item:potion",
        "qty_delta": 2,
        "label": "Potion",
    }
    assert client.post("/v1/pilot/player-inventory", json=body).status_code == 401
    r = client.post("/v1/pilot/player-inventory", json=body, headers={"X-LBG-Service-Token": "secret"})
    assert r.status_code == 200
    assert r.json().get("ok") is True
