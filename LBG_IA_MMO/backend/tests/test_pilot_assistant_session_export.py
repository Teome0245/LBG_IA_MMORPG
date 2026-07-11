from fastapi.testclient import TestClient


def test_assistant_session_export_sanitizes_mmo_keys() -> None:
    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/assistant/session-summary/export",
        json={
            "notes": "  objectif du jour  ",
            "session_summary": {
                "tracked_quest": "aide au village",
                "player_note": "ok",
                "secret_mail": "must drop",
            },
            "mmo_bridge": {"source": "mmo_session_summary", "imported_at": "2026-05-06T10:00:00Z", "extra": "x"},
            "history": [
                {"kind": "proposal", "capability": "desktop_control", "text": "x" * 900},
                {"bad": True},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    export = data["export"]
    assert export["kind"] == "assistant_voluntary_session_summary"
    assert export["sanitized"] is True
    assert export["notes"] == "objectif du jour"
    assert "secret_mail" not in export.get("session_summary", {})
    assert export["session_summary"]["tracked_quest"] == "aide au village"
    assert export["mmo_bridge"]["source"] == "mmo_session_summary"
    assert "extra" not in export["mmo_bridge"]
    assert len(export["history"]) == 1
    assert len(export["history"][0]["text"]) <= 500


def test_assistant_session_export_empty_payload_ok() -> None:
    from backend.main import app

    client = TestClient(app)
    r = client.post("/v1/pilot/assistant/session-summary/export", json={})
    assert r.status_code == 200
    export = r.json()["export"]
    assert export["voluntary"] is True
    assert "history" not in export
    assert "session_summary" not in export


def test_assistant_session_mmo_bridge_returns_context_patch() -> None:
    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/assistant/session-summary/mmo-bridge",
        json={
            "notes": "session test",
            "session_summary": {"tracked_quest": "quête village", "secret": "drop"},
            "mmo_bridge": {"source": "mmo_session_summary", "via": "test"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    patch = data["context_patch"]
    assert patch["session_summary"]["tracked_quest"] == "quête village"
    assert "secret" not in patch["session_summary"]
    assert patch["mmo_bridge"]["source"] == "mmo_session_summary"
    assert patch["mmo_bridge"]["via"] == "test"
    assert data.get("hint")
