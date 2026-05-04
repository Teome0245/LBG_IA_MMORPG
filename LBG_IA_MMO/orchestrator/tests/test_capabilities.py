from fastapi.testclient import TestClient

from orchestrator.main import app


def test_list_capabilities() -> None:
    client = TestClient(app)
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "capabilities" in data
    names = {c["name"] for c in data["capabilities"]}
    assert "npc_dialogue" in names
    assert "world_aid" in names
    assert "devops_probe" in names
    assert "project_pm" in names
    assert "desktop_control" in names
    assert "prototype_game" in names
    assert "unknown" in names
