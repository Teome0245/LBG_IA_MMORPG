"""Tests spawn playbook Infographiste IA."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_infographiste_job import infographiste_context, run_spawn


def test_infographiste_context_flags():
    ctx = infographiste_context()
    assert ctx["infographiste_ia"] is True
    assert ctx["subproject"] == "infographiste_ia"


def test_spawn_creates_dev_game_infographiste_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_INFOGRAPHISTE_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")

    def fake_create(**kwargs):
        assert kwargs["role"] == "dev_game"
        assert kwargs["context"]["infographiste_ia"] is True
        return {
            "task_id": "i1",
            "created": {"id": "i1"},
            "ran": {"id": "i1", "status": "done", "result": {"kind": "infographiste_workflow", "ok": True}},
        }

    with patch("lbg_agents.spawn_team_infographiste_job.create_and_run_team_task", fake_create):
        out = run_spawn()
    assert out["spawned"] is True
    assert out["task_ok"] is True


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_INFOGRAPHISTE_JOB_STATE", str(state_file))
    state_file.write_text(json.dumps({"last_spawn_ts": time.time()}) + "\n", encoding="utf-8")
    out = run_spawn()
    assert out["outcome"] == "cooldown"
