"""Tests spawn playbooks ops équipe (stockage + Ollama)."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from lbg_agents.spawn_team_ops_ollama_job import run_spawn as run_ollama
from lbg_agents.spawn_team_ops_storage_job import run_spawn as run_storage


def test_storage_skips_ok_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_OPS_STORAGE_JOB_STATE", str(tmp_path / "state.json"))
    with patch(
        "lbg_agents.spawn_team_ops_storage_job.probe_proxmox_storage_local",
        return_value={"ok": True, "outcome": "ok", "data_percent": 42},
    ):
        out = run_storage()
    assert out["spawned"] is False
    assert out["outcome"] == "ok"


def test_storage_spawns_on_warn(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_OPS_STORAGE_JOB_STATE", str(tmp_path / "state.json"))
    storage = {"ok": True, "outcome": "warn", "data_percent": 88}

    with patch("lbg_agents.spawn_team_ops_storage_job.probe_proxmox_storage_local", return_value=storage):
        with patch(
            "lbg_agents.spawn_team_ops_storage_job.create_and_run_team_task",
            return_value={
                "task_id": "ops-st-1",
                "ran": {"status": "done", "result": {"kind": "ops_storage", "ok": True}},
            },
        ) as mock_create:
            out = run_storage()

    assert out["spawned"] is True
    assert out["task_id"] == "ops-st-1"
    mock_create.assert_called_once()
    call_kw = mock_create.call_args.kwargs
    assert call_kw["role"] == "ops"
    assert call_kw["context"]["ops_kind"] == "proxmox_storage"


def test_ollama_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_TEAM_OPS_OLLAMA_JOB_STATE", str(state_file))
    state_file.write_text(json.dumps({"last_spawn_ts": time.time()}) + "\n", encoding="utf-8")
    out = run_ollama()
    assert out["spawned"] is False
    assert out["outcome"] == "cooldown"


def test_ollama_spawn_creates_ops_task(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_TEAM_OPS_OLLAMA_JOB_STATE", str(tmp_path / "state.json"))
    with patch(
        "lbg_agents.spawn_team_ops_ollama_job.create_and_run_team_task",
        return_value={
            "task_id": "ops-ol-1",
            "ran": {"status": "done", "result": {"kind": "ops_ollama", "ok": True}},
        },
    ) as mock_create:
        out = run_ollama()
    assert out["spawned"] is True
    assert out["task_ok"] is True
    assert mock_create.call_args.kwargs["context"]["ops_kind"] == "ollama"
