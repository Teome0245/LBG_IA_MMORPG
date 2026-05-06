from fastapi.testclient import TestClient

from orchestrator.main import app


def test_action_proposal_notepad_append() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "ouvre notepad et écris bonjour Lyra",
            "context": {"desktop_default_notepad_path": r"C:\Users\Public\notes.txt"},
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action_context_key"] == "desktop_action"
    assert proposal["action"]["kind"] == "notepad_append"
    assert proposal["action"]["path"] == r"C:\Users\Public\notes.txt"
    assert "bonjour Lyra" in proposal["action"]["text"]
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_web_search() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "cherche sur internet le site de Cursor AI", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action"]["kind"] == "search_web_open"
    assert proposal["action"]["query"] == "Cursor AI"
    assert proposal["context_patch"]["desktop_action"]["kind"] == "search_web_open"


def test_action_proposal_mail_preview_sender() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "regarde si j'ai un mail de Intel", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "desktop_control"
    assert proposal["action"]["kind"] == "mail_imap_preview"
    assert proposal["action"]["from_contains"] == "Intel"
    assert proposal["context_patch"]["desktop_dry_run"] is True


def test_action_proposal_infra_selfcheck() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "ops:1", "text": "vérifie l'état du backend et de l'orchestrateur", "context": {}},
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal["capability"] == "devops_probe"
    assert proposal["action_context_key"] == "devops_action"
    assert proposal["action"] == {"kind": "selfcheck"}
    assert proposal["context_patch"] == {"devops_action": {"kind": "selfcheck"}}


def test_action_proposal_no_match() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={"actor_id": "user:1", "text": "raconte-moi une histoire de taverne", "context": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["proposal"] is None
    assert "Aucune action" in data["reason"]


def test_action_proposal_mmo_bridge_opengame_prototype() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "forge un prototype sandbox pour une évolution MMO",
            "context": {
                "session_summary": {"tracked_quest": "aide au village", "player_note": "hier"},
                "mmo_bridge": {"source": "mmo_session_summary", "imported_at": "2026-05-06T10:00:00Z"},
            },
        },
    )
    assert r.status_code == 200
    proposal = r.json()["proposal"]
    assert proposal is not None
    assert proposal["capability"] == "prototype_game"
    assert proposal["action"]["kind"] == "generate_prototype"
    assert proposal["source"] == "mmo_session_bridge"
    assert proposal["mmo_trace"]["bridge_source"] == "mmo_session_summary"
    assert "desktop_action" not in proposal["context_patch"]
    assert proposal["context_patch"].get("opengame_dry_run") is True


def test_action_proposal_mmo_dev_requires_explicit_bridge() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/action-proposal",
        json={
            "actor_id": "user:1",
            "text": "forge un prototype sandbox",
            "context": {"session_summary": {"tracked_quest": "x"}},
        },
    )
    assert r.status_code == 200
    assert r.json()["proposal"] is None
