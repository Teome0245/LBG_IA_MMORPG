from fastapi.testclient import TestClient

from orchestrator.main import app


def test_route_intent_dialogue() -> None:
    client = TestClient(app)
    r = client.post("/v1/route", json={"actor_id": "player:1", "text": "Je veux parler au forgeron", "context": {}})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] in {"npc_dialogue", "unknown"}
    assert 0.0 <= data["confidence"] <= 1.0
    assert "routed_to" in data
    out = data["output"]
    assert out["capability"] in {"npc_dialogue", "unknown"}
    assert out.get("agent") == "minimal_stub"
    assert "handler" in out


def test_route_intent_forces_dialogue_when_npc_name_present() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "player:1",
            "text": "Une chambre pour la nuit, s'il vous plaît.",
            "context": {"npc_name": "Mara l’aubergiste"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "npc_dialogue"
    assert data["routed_to"] == "agent.dialogue"
    assert data["output"]["capability"] == "npc_dialogue"


def test_route_intent_prefers_quest_even_with_npc_name() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "player:1",
            "text": "J'ai une mission pour toi.",
            "context": {"npc_name": "Mara l’aubergiste"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "quest_request"
    assert data["routed_to"] == "agent.quests"
    assert data["output"]["capability"] == "quest_request"

