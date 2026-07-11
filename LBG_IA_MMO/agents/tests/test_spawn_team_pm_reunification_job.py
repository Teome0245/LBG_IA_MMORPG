"""Tests spawn playbook brief réunification → tâche équipe pm."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_pm_reunification_job import reunification_context, run_spawn


def test_spawn_skips_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_PM_REUNIFICATION_JOB_ENABLED", "0")
    monkeypatch.setenv("LBG_TEAM_PM_REUNIFICATION_JOB_STATE", str(tmp_path / "state.json"))
    out = run_spawn()
    assert out["outcome"] == "skipped"
    assert out["spawned"] is False


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_PM_REUNIFICATION_JOB_STATE", str(state_file))
    state_file.write_text(
        json.dumps({"last_spawn_ts": time.time(), "last_task_id": "t-old"}) + "\n",
        encoding="utf-8",
    )
    out = run_spawn()
    assert out["spawned"] is False
    assert out["outcome"] == "cooldown"


def test_reunification_context_flags():
    ctx = reunification_context()
    assert ctx["reunification_brief"] is True
    assert ctx["_team_pm_reunification_spawn"] is True
    assert ctx["pm_include_plan"] is True


def test_spawn_creates_and_runs_pm_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_PM_REUNIFICATION_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")

    calls: list[tuple[str, str]] = []

    def fake_create_and_run(**kwargs):
        calls.append(("create", kwargs["role"]))
        assert kwargs["role"] == "pm"
        assert kwargs["actor_id"] == "system:team_pm_reunification"
        assert kwargs["context"]["reunification_brief"] is True
        return {
            "task_id": "task-pm-1",
            "created": {"id": "task-pm-1", "status": "queued"},
            "ran": {
                "id": "task-pm-1",
                "status": "done",
                "result": {"kind": "pm_brief", "ok": True, "reunification": True},
            },
        }

    with patch("lbg_agents.spawn_team_pm_reunification_job.create_and_run_team_task", fake_create_and_run):
        out = run_spawn()

    assert out["spawned"] is True
    assert out["task_id"] == "task-pm-1"
    assert out["task_status"] == "done"
    assert out["task_ok"] is True
    assert calls == [("create", "pm")]
