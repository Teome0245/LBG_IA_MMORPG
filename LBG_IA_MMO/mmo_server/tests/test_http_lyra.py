from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from http_app import app


def test_healthz() -> None:
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json().get("ok") is True


def test_world_lyra_default_npc() -> None:
    with TestClient(app) as client:
        r = client.get("/v1/world/lyra", params={"npc_id": "npc:smith"})
        assert r.status_code == 200
        data = r.json()
        assert data["npc_id"] == "npc:smith"
        ly = data["lyra"]
        assert ly["meta"]["source"] == "mmo_world"
        assert "hunger" in ly["gauges"]
        rep = ly["meta"]["reputation"]
        assert isinstance(rep, dict)
        assert isinstance(rep.get("value"), int)


def test_world_lyra_unknown_npc_404() -> None:
    with TestClient(app) as client:
        r = client.get("/v1/world/lyra", params={"npc_id": "npc:nope"})
        assert r.status_code == 404


def test_internal_reputation_updates_world_lyra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_MMO_INTERNAL_TOKEN", raising=False)
    with TestClient(app) as client:
        before = client.get("/v1/world/lyra", params={"npc_id": "npc:smith"}).json()["lyra"]["meta"]["reputation"]["value"]
        r = client.post("/internal/v1/npc/npc:smith/reputation", json={"delta": 7})
        assert r.status_code == 200
        after = client.get("/v1/world/lyra", params={"npc_id": "npc:smith"}).json()["lyra"]["meta"]["reputation"]["value"]
        assert after == before + 7


def test_internal_reputation_requires_token_if_configured() -> None:
    old = os.environ.get("LBG_MMO_INTERNAL_TOKEN")
    os.environ["LBG_MMO_INTERNAL_TOKEN"] = "secret"
    try:
        with TestClient(app) as client:
            r1 = client.post("/internal/v1/npc/npc:smith/reputation", json={"delta": 1})
            assert r1.status_code == 401
            r2 = client.post(
                "/internal/v1/npc/npc:smith/reputation",
                headers={"X-LBG-Service-Token": "secret"},
                json={"delta": 1},
            )
            assert r2.status_code == 200
    finally:
        if old is None:
            os.environ.pop("LBG_MMO_INTERNAL_TOKEN", None)
        else:
            os.environ["LBG_MMO_INTERNAL_TOKEN"] = old
