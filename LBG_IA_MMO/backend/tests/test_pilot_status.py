import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_pilot_status_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DIALOGUE_URL", raising=False)
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    monkeypatch.delenv("LBG_AGENT_COMBAT_URL", raising=False)
    monkeypatch.delenv("LBG_MMO_SERVER_URL", raising=False)
    monkeypatch.delenv("LBG_MMO_INTERNAL_TOKEN", raising=False)
    client = TestClient(app)
    r = client.get("/v1/pilot/status")
    assert r.status_code == 200
    data = r.json()
    assert data["backend"] == "ok"
    assert "orchestrator" in data
    assert data["orchestrator"] in ("ok", "error", "unknown")
    assert data.get("agent_dialogue") == "skipped"
    assert data.get("agent_dialogue_url") is None
    assert data.get("agent_dialogue_info") is None
    assert data.get("agent_quests") == "skipped"
    assert data.get("agent_quests_url") is None
    assert data.get("agent_quests_info") is None
    assert data.get("agent_combat") == "skipped"
    assert data.get("agent_combat_url") is None
    assert data.get("agent_combat_info") is None
    assert data.get("mmo_server") == "skipped"
    assert data.get("mmo_server_url") is None
