"""Routes HTTP joueurs IA Core3 génériques."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_core3_player_tick_route(monkeypatch):
    monkeypatch.setattr(
        "lbg_agents.core3_player_autonomy.player_autonomy_tick",
        lambda player_id, *, via=None: {
            "ok": True,
            "player_id": player_id,
            "via": via,
            "action": "perform",
        },
    )
    client = TestClient(app)
    resp = client.post("/v1/core3/players/nix/tick", json={"via": "sidecar"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["player_id"] == "nix"
    assert data["via"] == "sidecar"
