"""Tests suivi QA → PM/ops (phase C)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ["LBG_TEAM_QA_FOLLOWUP_ENABLED"] = "1"

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.qa_followup import auto_run_followup_tasks, maybe_spawn_after_qa_failure  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_qa_followup_spawns_pm_on_failure() -> None:
    task = team_store.create_task(
        role="qa",
        objective="smoke",
        actor_id="u:qa",
    )
    team_store.update_task(
        task.id,
        status="failed",
        result={"kind": "qa_smoke", "ok": False, "smoke_script": {"ok": False, "exit_code": 1}},
    )
    refreshed = team_store.get_task(task.id)
    assert refreshed is not None
    ids = maybe_spawn_after_qa_failure(refreshed)
    assert len(ids) >= 1
    pm_tasks = team_store.list_tasks(role="pm", actor_id="system:team_qa_followup")
    assert len(pm_tasks) >= 1
    again = team_store.get_task(task.id)
    assert again is not None
    assert again.context.get("_qa_followup_spawned") is True
    assert maybe_spawn_after_qa_failure(again) == []


def test_qa_followup_spawns_ops_and_dev_on_smoke_failure() -> None:
    task = team_store.create_task(role="qa", objective="smoke", actor_id="u:qa")
    team_store.update_task(
        task.id,
        status="failed",
        result={
            "kind": "qa_smoke",
            "ok": False,
            "smoke_script": {"ok": False, "exit_code": 2, "skipped": False},
        },
    )
    refreshed = team_store.get_task(task.id)
    assert refreshed is not None
    ids = maybe_spawn_after_qa_failure(refreshed)
    assert len(ids) >= 3
    roles = {team_store.get_task(i).role for i in ids if team_store.get_task(i)}
    assert "pm" in roles
    assert "ops" in roles
    assert "dev_game" in roles


def test_auto_run_pm_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_QA_FOLLOWUP_AUTO_RUN_PM", "1")

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to, "brief": "triage ok"}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    task = team_store.create_task(role="qa", objective="smoke", actor_id="u:qa")
    team_store.update_task(
        task.id,
        status="failed",
        result={"kind": "qa_smoke", "ok": False, "smoke_script": {"ok": False, "exit_code": 1}},
    )
    refreshed = team_store.get_task(task.id)
    assert refreshed is not None
    ids = maybe_spawn_after_qa_failure(refreshed)
    auto_run_followup_tasks(ids)
    pm_tasks = team_store.list_tasks(role="pm", actor_id="system:team_qa_followup")
    assert pm_tasks
    assert pm_tasks[0].status == "done"
    assert pm_tasks[0].result.get("kind") == "pm_brief"


def test_auto_run_pm_followup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_QA_FOLLOWUP_AUTO_RUN_PM", "0")
    task = team_store.create_task(role="qa", objective="smoke", actor_id="u:qa")
    team_store.update_task(
        task.id,
        status="failed",
        result={"kind": "qa_smoke", "ok": False, "smoke_script": {"ok": False, "exit_code": 1}},
    )
    refreshed = team_store.get_task(task.id)
    assert refreshed is not None
    ids = maybe_spawn_after_qa_failure(refreshed)
    auto_run_followup_tasks(ids)
    pm_tasks = team_store.list_tasks(role="pm", actor_id="system:team_qa_followup")
    assert pm_tasks
    assert pm_tasks[0].status == "queued"


def test_qa_followup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_QA_FOLLOWUP_ENABLED", "0")
    task = team_store.create_task(role="qa", objective="x", actor_id="u:qa")
    team_store.update_task(task.id, status="failed", result={"ok": False})
    refreshed = team_store.get_task(task.id)
    assert refreshed is not None
    assert maybe_spawn_after_qa_failure(refreshed) == []


def test_approval_token_devops_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_TEAM_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "devops-secret")
    assert team_roles.approval_token_valid("devops-secret") is True
    assert team_roles.approval_token_valid("wrong") is False
