"""Routes HTTP /v1/lia/* (incarnation)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app


def test_lia_connect_route(monkeypatch):
    monkeypatch.setattr(
        "lbg_agents.lia_connection.connect_lia",
        lambda **kw: {"ok": True, "outcome": "connected", **kw},
    )
    client = TestClient(app)
    resp = client.post("/v1/lia/connect", json={"wait": True, "wait_s": 60})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "connected"


def test_lia_hear_route(monkeypatch):
    monkeypatch.setattr(
        "lbg_agents.lia_orchestrator.hear_player_message",
        lambda *, from_player, text: {
            "ok": True,
            "incarnation": True,
            "from": from_player,
            "heard": text,
        },
    )
    client = TestClient(app)
    resp = client.post("/v1/lia/hear", json={"from_player": "Teome", "text": "Bonjour"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["incarnation"] is True
