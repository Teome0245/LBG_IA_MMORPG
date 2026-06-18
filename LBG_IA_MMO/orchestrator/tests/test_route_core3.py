"""Routage intent core3_bot_action (Phase C)."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_route_core3_action_explicit():
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "p:1",
            "text": "Salue les voyageurs.",
            "context": {
                "core3_action": {"kind": "npc_think", "npc_id": "npc:core3_scribe"},
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "core3_bot_action"
    assert data["routed_to"] == "agent.core3"


def test_route_core3_player_think_explicit():
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "orchestrator:nix",
            "text": "Observe le terrain.",
            "context": {
                "core3_action": {"kind": "player_think", "player": "Nix", "enqueue": True},
                "core3_player_id": "nix",
                "core3_autonomy": True,
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "core3_bot_action"
    assert data["routed_to"] == "agent.core3"


def test_core3_capability_registered():
    from shared_registry import capability_registry

    cap = capability_registry.get("core3_bot_action")
    assert cap is not None
    assert cap.routed_to == "agent.core3"
