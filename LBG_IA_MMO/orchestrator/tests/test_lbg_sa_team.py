"""Tests API LBG_SA + kickoff Team."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from lbg_sa.memory_store import reset_memory_cache_for_tests
from lbg_sa.team_submit import enqueue_lbg_sa_kickoff_tasks
from main import app
from team import store as team_store


@pytest.fixture(autouse=True)
def _team_memory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_memory_cache_for_tests()
    monkeypatch.setenv("LBG_TEAM_DB_PATH", ":memory:")
    monkeypatch.setenv("LBG_STUDIOS_AGENTS_MEMORY_ROOT", str(tmp_path / "mem"))
    os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
    team_store.reset_for_tests()


def test_lbg_sa_meta_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/lbg_sa/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "phase0"
    assert body["product"] == "LBG Studios Agents"
    assert body["alias"] == "LBG_SA"
    assert len(body["modules"]) >= 6
    assert "atlas_llm" in {m["id"] for m in body["modules"]}


def test_team_plan_lbg_sa_keywords() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "lancer lbg_sa studios et mémoire équipe", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    roles = {p["role"] for p in r.json()["proposals"]}
    assert "pm" in roles
    assert "qa" in roles


def test_team_plan_legacy_fable5_keywords() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "lancer fable5 partitions et mémoire équipe", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    proposals = r.json()["proposals"]
    roles = {p["role"] for p in proposals}
    assert "pm" in roles
    assert "qa" in roles
    lbg = [p for p in proposals if (p.get("context") or {}).get("subproject") == "lbg_sa"]
    assert {p["role"] for p in lbg} >= {"pm", "qa"}


def test_kickoff_enqueue_three_tasks() -> None:
    out = enqueue_lbg_sa_kickoff_tasks(actor_id="u:lbg_sa", force=True)
    assert out["ok"] is True
    tasks = out["tasks"]
    assert len(tasks) == 3
    roles = {t["role"] for t in tasks}
    assert roles == {"pm", "qa", "admin_infra"}


def test_kickoff_api_idempotent() -> None:
    client = TestClient(app)
    r1 = client.post("/v1/lbg_sa/team/kickoff", json={"actor_id": "pilot:lbg_sa", "force": True})
    assert r1.status_code == 200
    assert len(r1.json()["tasks"]) == 3
    r2 = client.post("/v1/lbg_sa/team/kickoff", json={"actor_id": "pilot:lbg_sa", "force": False})
    assert r2.status_code == 200
    assert r2.json().get("skipped") == "kickoff_batch_exists"
    assert r2.json()["tasks"] == []
