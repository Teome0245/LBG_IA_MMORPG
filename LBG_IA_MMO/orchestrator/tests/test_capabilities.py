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
    assert "devops_probe" in names
    assert "unknown" in names
