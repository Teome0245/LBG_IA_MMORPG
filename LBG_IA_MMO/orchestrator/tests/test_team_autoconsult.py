"""Tests round autoconsultation — équipe Fable (Thémis + spécialistes)."""

from __future__ import annotations

import os
from typing import Any

import pytest

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.agent_registry import list_agents_summary, load_agent_declarations  # noqa: E402
from team.autoconsult_workflow import (  # noqa: E402
    execute_autoconsult_workflow,
    resolve_autoconsult_workflow,
)
from team.models import TeamTask  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_agent_registry_loads_declarations() -> None:
    decls = load_agent_declarations()
    assert len(decls) >= 9
    ids = {str(d.get("agent_id")) for d in decls}
    assert "studio_pm_themis" in ids
    assert "godot_dev_iris" in ids
    assert "godot_dev_hermes" in ids


def test_team_meta_agents_summary() -> None:
    agents = list_agents_summary()
    assert len(agents) >= 9
    assert any(a.get("persona") == "iris" for a in agents)
    assert any(a.get("display_name") for a in agents)


def test_resolve_autoconsult_from_context() -> None:
    task = TeamTask(
        id="t1",
        role="pm",
        objective="brief",
        context={"autoconsult_round": True},
    )
    assert resolve_autoconsult_workflow(task) is True


def test_team_plan_includes_autoconsult() -> None:
    proposals = team_roles.plan_from_objective("round autoconsultation équipe fable", actor_id="u:plan")
    pm = [p for p in proposals if p["role"] == "pm"]
    assert pm
    assert (pm[0].get("context") or {}).get("autoconsult_round") is True


def test_autoconsult_workflow_collects_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "team.autoconsult_workflow._qa_probe",
        lambda: {"track": "qa_health", "ok": True, "checks": []},
    )
    monkeypatch.setattr(
        "team.autoconsult_workflow._ops_probe",
        lambda: {"track": "ops_orchestrator", "ok": True},
    )
    monkeypatch.setattr(
        "team.autoconsult_workflow._iris_probe",
        lambda: {"track": "iris_m9", "ok": True, "probes": []},
    )
    monkeypatch.setattr(
        "team.autoconsult_workflow._hermes_probe",
        lambda: {"track": "hermes_soe", "ok": True, "gaps": [], "probes": []},
    )
    monkeypatch.setattr(
        "team.autoconsult_workflow._pygmalion_probe",
        lambda: {"track": "infographiste", "ok": True},
    )
    monkeypatch.setattr("team.autoconsult_workflow.followup_auto_run", lambda: False)

    def fake_dispatch(agent: str, **kwargs: Any) -> dict[str, object]:
        return {"agent": agent, "text": "brief ok"}

    task = TeamTask(
        id="ac1",
        role="pm",
        objective="Round autoconsultation",
        context={"autoconsult_round": True},
    )
    out = execute_autoconsult_workflow(task, fake_dispatch)
    assert out["kind"] == "autoconsult_workflow"
    assert out["ok"] is True
    assert len(out["probes"]) == 5
    assert out["agents_count"] == len(list_agents_summary())


def test_pm_role_routes_to_autoconsult(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_autoconsult(task: TeamTask, dispatch: Any) -> dict[str, object]:
        called["task_id"] = task.id
        return {"kind": "autoconsult_workflow", "ok": True, "probes": []}

    monkeypatch.setattr("team.roles.execute_autoconsult_workflow", fake_autoconsult)
    monkeypatch.setattr("team.roles.resolve_autoconsult_workflow", lambda t: True)

    task = team_store.create_task(
        role="pm",
        objective="Round autoconsultation équipe",
        actor_id="u:test",
        context={"autoconsult_round": True},
    )
    result = team_roles.run_task(task.id)
    assert result is not None
    assert result.status == "done"
    assert called.get("task_id") == task.id
