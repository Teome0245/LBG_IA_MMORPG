"""Tests workflow dev_game (forge + action_proposal)."""

from __future__ import annotations

import os

import pytest

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"

from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.dev_game_workflow import execute_dev_game_workflow  # noqa: E402


@pytest.fixture(autouse=True)
def _reset() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_dev_game_workflow_includes_forge_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_DEV_GAME_FORGE_ENABLED", "1")
    monkeypatch.setenv("LBG_TEAM_DEV_GAME_AUTO_RUN_FORGE", "0")

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    task = team_store.create_task(
        role="dev_game",
        objective="Analyser bug gameplay — prototype sandbox dry-run",
        actor_id="u:dev",
        context={"dev_game_focus": True, "_qa_followup": True, "qa_failure_summary": {"smoke_ok": False}},
    )
    result = execute_dev_game_workflow(task, fake_dispatch)
    assert result["kind"] == "dev_game_workflow"
    assert result["ok"] is True
    prop = result.get("action_proposal")
    assert isinstance(prop, dict)
    assert prop.get("capability") == "prototype_game"
    assert prop.get("source") == "team_dev_game"
    assert "forge_dry_run" not in result


def test_dev_game_workflow_auto_run_forge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_DEV_GAME_FORGE_ENABLED", "1")
    monkeypatch.setenv("LBG_TEAM_DEV_GAME_AUTO_RUN_FORGE", "1")
    calls: list[str] = []

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        calls.append(routed_to)
        return {"ok": True, "agent": routed_to}

    task = team_store.create_task(
        role="dev_game",
        objective="forge prototype sandbox pour correctif smoke",
        actor_id="u:dev",
        context={"dev_game_focus": True},
    )
    result = execute_dev_game_workflow(task, fake_dispatch)
    assert result.get("forge_dry_run") is not None
    assert "agent.opengame" in calls
