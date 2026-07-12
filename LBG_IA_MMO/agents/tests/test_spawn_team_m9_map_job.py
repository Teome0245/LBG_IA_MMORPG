"""Tests spawn playbook jalon M9 carte/minimap."""

from __future__ import annotations

import json
from unittest.mock import patch

from lbg_agents.spawn_team_m9_map_job import next_track, run_spawn, track_context


def test_track_context():
    ctx = track_context("m9b")
    assert ctx["m9_track"] == "m9b"
    assert ctx["subproject"] == "prime_client_2d"


def test_next_track_rotates():
    assert next_track({"last_track": "m9a"}) == "m9b"
    assert next_track({"last_track": "m9_full"}) == "m9a"


def test_spawn_m9_track(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_M9_MAP_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("LBG_TEAM_M9_MAP_JOB_TRACK", "m9c")

    def fake_create(**kwargs):
        assert kwargs["role"] == "dev_game"
        assert kwargs["context"]["m9_track"] == "m9c"
        return {
            "task_id": "t-m9",
            "status": "done",
            "result": {"kind": "m9_map_workflow", "ok": False},
        }

    with patch("lbg_agents.spawn_team_m9_map_job.create_and_run_team_task", fake_create):
        result = run_spawn()
    assert result["spawned"] is True
    assert result["track"] == "m9c"
    assert json.loads(json.dumps(result))["task_id"] == "t-m9"
