"""Tests couche proactive (hybrid_proactive_agent + jobs auto)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("LBG_JOBS_RUNNER_ENABLED", "0")
os.environ.setdefault("LBG_PROACTIVE_ENABLED", "0")

from services import proactive as svc_proactive
from services import jobs as svc_jobs


@pytest.fixture(autouse=True)
def _reset_proactive(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("LBG_PROACTIVE_STATE_PATH", str(tmp_path / "proactive.json"))
    svc_proactive._runtime.engine.reset()
    svc_proactive._runtime.ticks = 0
    svc_proactive._runtime.last_auto_job_ts = 0.0
    svc_proactive._runtime.auto_jobs_spawned = 0


def test_observe_turn_returns_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PROACTIVE_ENABLED", "1")
    out = svc_proactive.observe_turn(
        actor_id="pilot:1",
        text="analyse le réseau",
        intent="network_inventory",
        context={},
    )
    assert "hints" in out
    assert out["hints"].get("hybrid_proactive_mode")
    assert isinstance(out.get("action"), dict)


def test_enrich_route_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PROACTIVE_ENABLED", "1")
    monkeypatch.setenv("LBG_PROACTIVE_ROUTE_HINTS", "1")
    body: dict = {"ok": True}
    svc_proactive.enrich_route_output(
        actor_id="ops:1",
        text="hello",
        intent="npc_dialogue",
        context={},
        out_body=body,
    )
    assert "proactive_hints" in body
    assert "proactive_action" in body


def test_tick_spawns_job_when_autonome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PROACTIVE_ENABLED", "1")
    monkeypatch.setenv("LBG_PROACTIVE_AUTO_JOBS", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    monkeypatch.setenv("LBG_PROACTIVE_MIN_JOB_INTERVAL_S", "0")
    monkeypatch.setenv("LBG_PROACTIVE_TENSION_JOB_THRESHOLD", "0.4")

    svc_proactive._runtime.engine.state.tension = 0.85
    svc_proactive._runtime.engine.state.mode = "autonome"
    svc_proactive._runtime.engine.state.silence_seconds_est = 120.0

    before = len(svc_jobs.list_jobs(actor_id=svc_proactive.proactive_actor_id()))
    svc_proactive._tick_once()
    after = svc_jobs.list_jobs(actor_id=svc_proactive.proactive_actor_id())
    assert len(after) == before + 1
    assert svc_proactive._runtime.last_job_id is not None
    assert after[0].objective


def test_tick_spawns_lia_job_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_PROACTIVE_ENABLED", "1")
    monkeypatch.setenv("LBG_PROACTIVE_AUTO_JOBS", "1")
    monkeypatch.setenv("LBG_PROACTIVE_LIA_JOBS", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    monkeypatch.setenv("LBG_PROACTIVE_MIN_JOB_INTERVAL_S", "0")
    monkeypatch.setenv("LBG_PROACTIVE_TENSION_JOB_THRESHOLD", "0.4")
    monkeypatch.setenv("LBG_CORE3_LIA_AUTONOMY_ENABLED", "0")
    monkeypatch.setattr(svc_proactive, "_tcp_open", lambda host, port, timeout_s=1.0: port == 8791)

    for job in svc_jobs.list_jobs():
        svc_jobs.cancel_job(job.id)
    svc_proactive._runtime.last_auto_job_ts = 0.0
    svc_proactive._runtime.engine.state.tension = 0.85
    svc_proactive._runtime.engine.state.mode = "autonome"
    svc_proactive._runtime.auto_jobs_spawned = 1

    svc_proactive._tick_once()
    jobs = svc_jobs.list_jobs(actor_id="orchestrator:lia")
    assert len(jobs) >= 1
    assert "lia" in jobs[0].objective.lower() or "mmo" in jobs[0].objective.lower()


def test_proactive_status_api() -> None:
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    r = client.get("/v1/proactive/status")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "mode" in data
