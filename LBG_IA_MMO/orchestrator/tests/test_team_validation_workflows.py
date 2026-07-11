"""Tests validation humaine + build Core3 workflows."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.human_summary import format_validation_summary  # noqa: E402


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M3", "0")
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M5", "0")


def test_human_summary_format() -> None:
    text = format_validation_summary(
        title="Test",
        probes=[{"track": "zb0_readiness", "ok": True, "checks": {"zb0_header": True}}],
        checklist=["Lancer Godot"],
    )
    assert "Test" in text
    assert "zb0_readiness" in text
    assert "Lancer Godot" in text


def test_core3_build_plan_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "Plan build Core3 ZB-0",
            "actor_id": "u:vulcan",
            "context": {"core3_build": True, "subproject": "core3_build"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    res = ran["result"]
    assert res["kind"] == "core3_build_workflow"
    assert res["persona"] == "Vulcan"
    assert res.get("human_summary")
    assert res.get("execute_mode") is False


def test_godot_validation_workflow_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "team.godot_validation_workflow.execute_godot_supervisor",
        lambda task: {"kind": "godot_supervisor", "ok": True, "tracks": [{"track": "sidecar_m1", "ok": True}]},
    )
    monkeypatch.setattr(
        "team.godot_validation_workflow._run_smoke_script",
        lambda name, extra_env=None: {"track": "smoke_test", "ok": True, "skipped": True},
    )

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "qa",
            "objective": "Valider client Godot",
            "actor_id": "u:qa",
            "context": {"godot_validation": True},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    res = ran["result"]
    assert res["kind"] == "godot_validation_workflow"
    assert "godot4 --path" in res.get("human_summary", "")
    assert res.get("launch_commands")
