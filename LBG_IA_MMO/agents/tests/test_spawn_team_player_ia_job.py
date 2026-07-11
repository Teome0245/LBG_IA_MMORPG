"""Tests spawn playbook player_ia → tâche équipe."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_player_ia_job import run_spawn


def test_spawn_player_ia_skips_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_PLAYER_IA_JOB_ENABLED", "0")
    monkeypatch.setenv("LBG_TEAM_PLAYER_IA_JOB_STATE", str(tmp_path / "state.json"))
    out = run_spawn()
    assert out["outcome"] == "skipped"


def test_spawn_player_ia_creates_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_PLAYER_IA_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")

    def fake_create(**kwargs):
        assert kwargs["role"] == "player_ia"
        return {
            "task_id": "t-pia-1",
            "ran": {"id": "t-pia-1", "status": "done", "result": {"kind": "player_ia_probe", "ok": True}},
        }

    with patch("lbg_agents.spawn_team_player_ia_job.create_and_run_team_task", fake_create):
        out = run_spawn()
    assert out["spawned"] is True
    assert out["task_id"] == "t-pia-1"
    assert out["task_ok"] is True


def test_spawn_player_ia_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_PLAYER_IA_JOB_STATE", str(state_file))
    state_file.write_text(json.dumps({"last_spawn_ts": time.time()}) + "\n", encoding="utf-8")
    out = run_spawn()
    assert out["outcome"] == "cooldown"
