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
    assert "dialogue_target" in data["output"].get("context_keys", [])


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


def test_route_intent_world_action_kind_forces_dialogue_even_for_quest_text() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "player:1",
            "text": "Propose-moi une quête simple.",
            "context": {
                "npc_name": "Mara l’aubergiste",
                "world_npc_id": "npc:innkeeper",
                "_require_action_json": True,
                "_world_action_kind": "quest",
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "npc_dialogue"
    assert data["routed_to"] == "agent.dialogue"
    assert data["output"]["capability"] == "npc_dialogue"


def test_route_intent_project_pm_classifier() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "player:1",
            "text": "Quel est le plan de route pour la release ?",
            "context": {},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "project_pm"
    assert data["routed_to"] == "agent.pm"
    out = data["output"]
    assert out["capability"] == "project_pm"
    assert out.get("agent") == "pm_stub"
    assert isinstance(out.get("brief"), dict)


def test_route_intent_project_pm_context_flag() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "svc:1",
            "text": "x",
            "context": {"pm_focus": True},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "project_pm"
    assert data["routed_to"] == "agent.pm"


def test_route_intent_desktop_action_forces_desktop_control() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "svc:desktop",
            "text": "Ignoré si desktop_action présent",
            "context": {"desktop_action": {"kind": "open_url", "url": "https://example.org"}},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "desktop_control"
    assert data["routed_to"] == "agent.desktop"
    out = data["output"]
    assert out["capability"] == "desktop_control"


def test_route_intent_opengame_action_forces_prototype_game() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "svc:opengame",
            "text": "Ignoré si opengame_action présent",
            "context": {
                "opengame_action": {
                    "kind": "generate_prototype",
                    "project_name": "snake",
                    "prompt": "Build a Snake prototype",
                }
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "prototype_game"
    assert data["routed_to"] == "agent.opengame"
    out = data["output"]
    assert out["capability"] == "prototype_game"
    assert out.get("agent") == "opengame_executor"
    assert out.get("outcome") == "dry_run"


def test_route_intent_world_action_forces_world_aid() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "svc:smoke",
            "text": "Ignoré si world_action présent",
            "context": {
                "world_npc_id": "npc:merchant",
                "world_action": {"kind": "aid", "hunger_delta": -0.2, "thirst_delta": -0.1, "reputation_delta": 5},
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "world_aid"
    assert data["routed_to"] == "agent.world"
    out = data["output"]
    assert out["capability"] == "world_aid"
    assert out.get("agent") == "world_stub"
    commit = out.get("commit") or {}
    assert isinstance(commit, dict)
    flags = commit.get("flags") or {}
    assert isinstance(flags, dict)
    assert "aid_hunger_delta" in flags

