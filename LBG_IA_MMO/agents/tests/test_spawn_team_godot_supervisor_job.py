"""Tests spawn playbook superviseur Godot."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_godot_supervisor_job import run_spawn, supervisor_context


def test_supervisor_context_flags():
    ctx = supervisor_context()
    assert ctx["godot_supervisor"] is True
    assert ctx["godot_mode"] == "full"


def test_spawn_creates_qa_godot_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_GODOT_SUPERVISOR_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")

    def fake_create(**kwargs):
        assert kwargs["role"] == "qa"
        assert kwargs["context"]["godot_supervisor"] is True
        return {
            "task_id": "g1",
            "created": {"id": "g1"},
            "ran": {"id": "g1", "status": "done", "result": {"kind": "godot_supervisor", "ok": True}},
        }

    with patch("lbg_agents.spawn_team_godot_supervisor_job.create_and_run_team_task", fake_create):
        out = run_spawn()
    assert out["spawned"] is True
    assert out["task_ok"] is True


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_GODOT_SUPERVISOR_JOB_STATE", str(state_file))
    state_file.write_text(json.dumps({"last_spawn_ts": time.time()}) + "\n", encoding="utf-8")
    out = run_spawn()
    assert out["outcome"] == "cooldown"
