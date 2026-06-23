"""Tests spawn job Pilot stockage Proxmox."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from lbg_agents.spawn_infra_storage_watchdog_job import run_spawn


def test_spawn_skips_when_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_STORAGE_WATCHDOG_STATE", str(tmp_path / "state.json"))
    fake_storage = {"ok": True, "outcome": "ok", "data_percent": 50.0}
    with patch("lbg_agents.spawn_infra_storage_watchdog_job.probe_proxmox_storage_local", return_value=fake_storage):
        out = run_spawn()
    assert out["spawned"] is False
    assert out["outcome"] == "ok"


def test_spawn_creates_job_on_warn(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_STORAGE_WATCHDOG_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    fake_storage = {"ok": True, "outcome": "warn", "data_percent": 87.0}
    job_resp = {"id": "job-test-1", "status": "running"}

    def fake_urlopen(req, timeout=20):
        assert req.full_url.endswith("/v1/jobs")
        body = json.loads(req.data.decode("utf-8"))
        assert body["actor_id"] == "system:storage_watchdog"
        assert body["auto_start"] is True
        resp = MagicMock()
        resp.read.return_value = json.dumps(job_resp).encode("utf-8")
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("lbg_agents.spawn_infra_storage_watchdog_job.probe_proxmox_storage_local", return_value=fake_storage):
        with patch("urllib.request.urlopen", fake_urlopen):
            out = run_spawn()
    assert out["spawned"] is True
    assert out["job_id"] == "job-test-1"


def test_spawn_respects_cooldown(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LBG_STORAGE_WATCHDOG_STATE", str(state_file))
    import time

    state_file.write_text(
        json.dumps({"last_spawn_ts": time.time(), "last_spawn_outcome": "warn"}) + "\n",
        encoding="utf-8",
    )
    fake_storage = {"ok": True, "outcome": "warn", "data_percent": 86.0}
    with patch("lbg_agents.spawn_infra_storage_watchdog_job.probe_proxmox_storage_local", return_value=fake_storage):
        out = run_spawn()
    assert out["spawned"] is False
