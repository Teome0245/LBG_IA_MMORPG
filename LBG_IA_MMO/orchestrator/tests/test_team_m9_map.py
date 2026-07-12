"""Tests jalon M9 — Scrapaltai carte + minimap (équipe virtuelle)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.m9_map_probe import audit_m9a_readiness, audit_m9b_readiness  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_audit_m9a_finds_map_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs/jalon_m9_scrapaltai_map_minimap.md").write_text("# M9\n", encoding="utf-8")
    (repo / "content/core3/world_poi").mkdir(parents=True)
    (repo / "content/core3/world_poi/scrapaltai.json").write_text("{}", encoding="utf-8")

    prime = tmp_path / "prime-client"
    maps = prime / "assets/maps"
    maps.mkdir(parents=True)
    (maps / "tatooine_map_config.json").write_text(
        json.dumps({"display_name": "Scrapaltai", "half_size": 6500}),
        encoding="utf-8",
    )
    (maps / "tatooine.svg").write_text("<svg/>", encoding="utf-8")
    (maps / "tatooine_pois.json").write_text("[]", encoding="utf-8")

    export_dir = repo / "tools/map_export"
    export_dir.mkdir(parents=True)
    (export_dir / "export_scrapaltai_for_godot.py").write_text("# ok\n", encoding="utf-8")
    (repo / "infra/scripts").mkdir(parents=True)
    (repo / "infra/scripts/sync_scrapaltai_poi_godot.sh").write_text("# ok\n", encoding="utf-8")

    monkeypatch.setattr("team.m9_map_probe._repo_root", lambda: repo)
    monkeypatch.setattr("team.m9_map_probe._prime_client_root", lambda: prime)
    out = audit_m9a_readiness()
    assert out["track"] == "m9a_readiness"
    assert out["ok"] is True


def test_audit_m9b_reports_gaps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prime = tmp_path / "prime-client"
    prime.mkdir()
    (prime / "scenes").mkdir()
    (prime / "scenes/main.tscn").write_text("[node name=\"Main\"]\n", encoding="utf-8")
    monkeypatch.setattr("team.m9_map_probe._prime_client_root", lambda: prime)
    out = audit_m9b_readiness()
    assert out["ok"] is False
    assert any("minimap" in g.lower() for g in out["gaps"])


def test_team_plan_includes_m9b() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "audit m9 minimap scrapaltai hud", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    dev = [p for p in r.json()["proposals"] if p["role"] == "dev_game"]
    assert any((p.get("context") or {}).get("m9_track") == "m9b" for p in dev)


def test_team_run_m9a_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to}

    def fake_m9a():
        return {"track": "m9a_readiness", "ok": False, "gaps": ["export pipeline manquant"]}

    monkeypatch.setattr("team.m9_map_workflow.audit_m9a_readiness", fake_m9a)
    team_roles.set_dispatch_for_tests(fake_dispatch)

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "Audit M9a Scrapaltai",
            "actor_id": "u:m9",
            "context": {"m9_track": "m9a"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    res = ran["result"]
    assert res["kind"] == "m9_map_workflow"
    assert res["track"] == "m9a"
    assert res["ok"] is False
