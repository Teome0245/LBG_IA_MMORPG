from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from http_app import app


def test_internal_aid_updates_gauges_and_rep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_MMO_INTERNAL_TOKEN", raising=False)
    with TestClient(app) as client:
        before = client.get("/v1/world/lyra", params={"npc_id": "npc:smith"}).json()["lyra"]
        r = client.post(
            "/internal/v1/npc/npc:smith/aid",
            json={"hunger_delta": -0.2, "thirst_delta": -0.1, "fatigue_delta": -0.3, "reputation_delta": 5},
        )
        assert r.status_code == 200
        after = client.get("/v1/world/lyra", params={"npc_id": "npc:smith"}).json()["lyra"]

        assert after["gauges"]["hunger"] <= before["gauges"]["hunger"]
        assert after["gauges"]["thirst"] <= before["gauges"]["thirst"]
        assert after["gauges"]["fatigue"] <= before["gauges"]["fatigue"]
        assert after["meta"]["reputation"]["value"] == before["meta"]["reputation"]["value"] + 5


def test_internal_aid_requires_token_if_configured() -> None:
    old = os.environ.get("LBG_MMO_INTERNAL_TOKEN")
    os.environ["LBG_MMO_INTERNAL_TOKEN"] = "secret"
    try:
        with TestClient(app) as client:
            r1 = client.post("/internal/v1/npc/npc:smith/aid", json={"reputation_delta": 1})
            assert r1.status_code == 401
            r2 = client.post(
                "/internal/v1/npc/npc:smith/aid",
                headers={"X-LBG-Service-Token": "secret"},
                json={"reputation_delta": 1},
            )
            assert r2.status_code == 200
    finally:
        if old is None:
            os.environ.pop("LBG_MMO_INTERNAL_TOKEN", None)
        else:
            os.environ["LBG_MMO_INTERNAL_TOKEN"] = old

