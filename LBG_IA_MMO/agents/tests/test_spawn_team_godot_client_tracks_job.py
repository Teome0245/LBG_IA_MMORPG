"""Tests spawn playbook client tracks M3/M5/ZB-0."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_godot_client_tracks_job import next_track, run_spawn, track_context


def test_track_context():
    ctx = track_context("soe_m3")
    assert ctx["godot_track"] == "soe_m3"


def test_next_track_rotates():
    assert next_track({"last_track": "soe_m3"}) == "soe_m5"
    assert next_track({"last_track": "client_live"}) == "soe_m3"


def test_spawn_dev_game_track(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_GODOT_CLIENT_TRACKS_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("LBG_TEAM_GODOT_CLIENT_TRACKS_JOB_TRACK", "zb0")

    def fake_create(**kwargs):
        assert kwargs["role"] == "dev_game"
        assert kwargs["context"]["godot_track"] == "zb0"
        return {
            "task_id": "t1",
            "created": {"id": "t1"},
            "ran": {"id": "t1", "status": "done", "result": {"kind": "godot_client_tracks_workflow", "ok": True}},
        }

    with patch("lbg_agents.spawn_team_godot_client_tracks_job.create_and_run_team_task", fake_create):
        out = run_spawn()
    assert out["spawned"] is True
    assert out["track"] == "zb0"


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_GODOT_CLIENT_TRACKS_JOB_STATE", str(state_file))
    state_file.write_text(json.dumps({"last_spawn_ts": time.time()}) + "\n", encoding="utf-8")
    out = run_spawn()
    assert out["outcome"] == "cooldown"
