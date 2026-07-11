"""Tests spawn playbook smoke quotidien → tâche équipe qa."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_qa_smoke_job import run_spawn


def test_spawn_skips_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_QA_SMOKE_JOB_ENABLED", "0")
    monkeypatch.setenv("LBG_TEAM_QA_SMOKE_JOB_STATE", str(tmp_path / "state.json"))
    out = run_spawn()
    assert out["outcome"] == "skipped"
    assert out["spawned"] is False


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_QA_SMOKE_JOB_STATE", str(state_file))
    state_file.write_text(
        json.dumps({"last_spawn_ts": time.time(), "last_task_id": "t-old"}) + "\n",
        encoding="utf-8",
    )
    out = run_spawn()
    assert out["spawned"] is False
    assert out["outcome"] == "cooldown"


def test_spawn_creates_and_runs_qa_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_QA_SMOKE_JOB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")

    calls: list[tuple[str, str]] = []

    def fake_api_json(method, url, body=None):
        calls.append((method, url))
        if method == "POST" and url.endswith("/v1/team/tasks"):
            assert body["role"] == "qa"
            assert body["actor_id"] == "system:team_qa_smoke"
            assert body["approval_required"] is False
            return {"id": "task-qa-1", "status": "queued"}
        if method == "POST" and url.endswith("/v1/team/tasks/task-qa-1/run"):
            return {
                "id": "task-qa-1",
                "status": "done",
                "result": {"kind": "qa_smoke", "ok": True},
            }
        raise AssertionError(f"unexpected call: {method} {url}")

    with patch("lbg_agents.spawn_team_qa_smoke_job._api_json", fake_api_json):
        out = run_spawn()

    assert out["spawned"] is True
    assert out["task_id"] == "task-qa-1"
    assert out["task_status"] == "done"
    assert out["task_ok"] is True
    assert len(calls) == 2


def test_spawn_reports_api_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_QA_SMOKE_JOB_STATE", str(tmp_path / "state.json"))

    def fake_urlopen(req, timeout=300):
        raise OSError("connexion refusée")

    with patch("urllib.request.urlopen", fake_urlopen):
        out = run_spawn()

    assert out["ok"] is False
    assert out["spawned"] is False
    assert "error" in out
