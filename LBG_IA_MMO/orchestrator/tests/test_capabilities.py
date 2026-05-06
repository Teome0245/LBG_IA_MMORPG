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

    by_name = {c["name"]: c for c in data["capabilities"]}
    desktop = by_name["desktop_control"]
    assert desktop["mode"] == "local_assistant"
    assert desktop["risk_level"] == "high"
    assert desktop["action_context_key"] == "desktop_action"
    assert desktop["input_schema"]["properties"]["context"]["required"] == ["desktop_action"]
    desktop_constraints = {c["name"] for c in desktop["constraints"]}
    assert {"dry_run_default", "allowlists_required", "approval_for_real_execution"} <= desktop_constraints

    dialogue = by_name["npc_dialogue"]
    assert dialogue["mode"] == "mmo_persona"
    dialogue_constraints = {c["name"] for c in dialogue["constraints"]}
    assert "no_private_desktop_context" in dialogue_constraints

    fallback = by_name["unknown"]
    assert fallback["protocol"] == "internal"
