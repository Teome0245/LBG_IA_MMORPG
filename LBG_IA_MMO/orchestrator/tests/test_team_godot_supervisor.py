"""Tests superviseur Godot équipe virtuelle."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.lbg_ws2_audit import audit_lbg_ws2_readiness  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db(monkeypatch: pytest.MonkeyPatch) -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M3", "0")
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M5", "0")


def test_lbg_ws2_audit_has_module() -> None:
    out = audit_lbg_ws2_readiness()
    assert out["track"] == "lbg_ws2_readiness"
    assert out["checks"].get("lbg_ws2_module") is True
    assert out["checks"].get("schema_zone_state_v2") is True


def test_team_plan_includes_godot_supervisor() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "supervise godot et lbg-ws/2 sur Prime", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    roles = {p["role"] for p in r.json()["proposals"]}
    assert "qa" in roles
    assert "dev_game" in roles


def test_team_run_godot_supervisor(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_probe(task):  # noqa: ANN001
        return {
            "kind": "player_ia_probe",
            "ok": True,
            "online_count": 3,
            "checks": [],
        }

    monkeypatch.setattr("team.godot_supervisor.probe_player_ia", fake_probe)
    monkeypatch.setenv("LBG_TEAM_GODOT_GATEWAY_SMOKE", "0")

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "qa",
            "objective": "Supervise Godot",
            "actor_id": "u:godot",
            "context": {"godot_supervisor": True, "godot_mode": "full"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "godot_supervisor"
    assert ran["result"]["ok"] is True
    tracks = {t["track"] for t in ran["result"]["tracks"]}
    assert "sidecar_m1" in tracks
    assert "lbg_ws2_readiness" in tracks
    assert "infographiste_assets" in tracks


def test_team_run_godot_client_workflow() -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to, "brief": {}}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "Audit lbg-ws/2 gateway Godot Prime",
            "actor_id": "u:devg",
            "context": {"godot_track": "lbg_ws2"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "godot_client_workflow"
    assert ran["result"].get("lbg_ws2_audit") is not None
