"""Tests workflow Infographiste IA (équipe virtuelle)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.infographiste_probe import probe_infographiste_assets  # noqa: E402
from team.role_aliases import enrich_task_view  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_infographiste_probe_structural_ok() -> None:
    out = probe_infographiste_assets(None)
    assert out["kind"] == "infographiste_probe"
    assert out["ok"] is True
    assert out["readiness"] in ("en_cours", "partiel")
    assert isinstance(out.get("glb_expected"), int)
    assert out["glb_expected"] >= 1


def test_team_plan_includes_infographiste() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "audit pipeline assets glb infographiste blender", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    proposals = r.json()["proposals"]
    dev = [p for p in proposals if p["role"] == "dev_game"]
    assert dev
    ctx = dev[0].get("context") or {}
    assert ctx.get("infographiste_ia") is True
    assert ctx.get("subproject") == "infographiste_ia"


def test_team_run_infographiste_workflow() -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to, "brief": {"subprojects": context.get("subprojects")}}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "Audit pipeline assets GLB Infographiste IA",
            "actor_id": "u:pygmalion",
            "context": {"infographiste_ia": True, "subproject": "infographiste_ia"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    res = ran["result"]
    assert res["kind"] == "infographiste_workflow"
    assert res["ok"] is True
    assert res["persona"] == "Pygmalion"
    probe = res.get("probe") or {}
    assert probe.get("kind") == "infographiste_probe"
    prop = res.get("action_proposal") or {}
    assert prop.get("source") == "team_infographiste_ia"


def test_enrich_task_view_pygmalion() -> None:
    view = enrich_task_view(
        {
            "role": "dev_game",
            "context": {"infographiste_ia": True, "subproject": "infographiste_ia"},
        }
    )
    assert view["role_alias"] == "Pygmalion"
    assert view["role_label"] == "Pygmalion (infographiste_ia)"


def test_godot_supervisor_includes_infographiste_track(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_probe(task):  # noqa: ANN001
        return {"kind": "player_ia_probe", "ok": True, "online_count": 2, "checks": []}

    monkeypatch.setattr("team.godot_supervisor.probe_player_ia", fake_probe)
    monkeypatch.setenv("LBG_TEAM_GODOT_GATEWAY_SMOKE", "0")

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "qa",
            "objective": "Supervise Godot full",
            "actor_id": "u:godot",
            "context": {"godot_supervisor": True, "godot_mode": "full"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    tracks = {t["track"] for t in ran["result"]["tracks"]}
    assert "infographiste_assets" in tracks
