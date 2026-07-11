"""Tests pistes client Godot M3/M5/ZB-0 (équipe virtuelle)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.lbg_ws2_audit import audit_zb0_readiness  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db(monkeypatch: pytest.MonkeyPatch) -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M3", "0")
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M5", "0")


def test_audit_zb0_finds_header_stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    new_mmo = tmp_path / "new_mmo"
    hdr = new_mmo / "lbg-mmo/server-core3/server/lbg"
    hdr.mkdir(parents=True)
    (hdr / "LbgZoneBridge.h").write_text("// stub\n", encoding="utf-8")
    (hdr / "LbgZoneBridge.cpp").write_text("// stub\n", encoding="utf-8")
    (hdr / "LbgZoneBridgeReadOnly.cpp").write_text("// stub\n", encoding="utf-8")
    (hdr / "LbgZoneBridgeTickTask.h").write_text("// stub\n", encoding="utf-8")
    (hdr / "LbgZoneBridgeInit.cpp").write_text("// stub\n", encoding="utf-8")
    zone_impl = new_mmo / "lbg-mmo/server-core3/server/zone"
    zone_impl.mkdir(parents=True)
    (zone_impl / "ZoneServerImplementation.cpp").write_text(
        "lbg::zonebridge::startZoneBridgeTick(_this);\n",
        encoding="utf-8",
    )
    cmake = new_mmo / "lbg-mmo/server-core3"
    cmake.mkdir(parents=True)
    (cmake / "CMakeLists.txt").write_text('file(GLOB_RECURSE lbg_sources "server/lbg/*.cpp")\n', encoding="utf-8")
    monkeypatch.setenv("LBG_NEW_MMO_ROOT", str(new_mmo))
    out = audit_zb0_readiness()
    assert out["track"] == "zb0_readiness"
    assert out["checks"]["zb0_header"] is True
    assert out["checks"]["zone_server_zb_hook"] is True
    assert out["ok"] is True


def test_team_plan_includes_soe_m3() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "audit soe m3 login zone udp prime", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    dev = [p for p in r.json()["proposals"] if p["role"] == "dev_game"]
    assert any((p.get("context") or {}).get("godot_track") == "soe_m3" for p in dev)


def test_team_run_zb0_track_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "Audit ZB-0 LbgZoneBridge",
            "actor_id": "u:zb",
            "context": {"godot_track": "zb0"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    res = ran["result"]
    assert res["kind"] == "godot_client_tracks_workflow"
    assert res["track"] == "zb0"
    probes = res.get("probes") or []
    assert any(p.get("track") == "zb0_readiness" for p in probes)


def test_team_run_soe_m3_track_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to}

    def fake_login():
        return {"track": "soe_m3_login", "ok": True, "login_ok": True}

    def fake_zone():
        return {"track": "soe_m3_zone", "ok": True, "zone_ok": True}

    monkeypatch.setattr("team.godot_client_tracks_workflow.probe_soe_m3_login", fake_login)
    monkeypatch.setattr("team.godot_client_tracks_workflow.probe_soe_m3_zone", fake_zone)
    team_roles.set_dispatch_for_tests(fake_dispatch)

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "SOE M3 audit",
            "actor_id": "u:m3",
            "context": {"godot_track": "soe_m3"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["ok"] is True
    prop = ran["result"].get("action_proposal") or {}
    assert prop.get("source") == "team_godot_soe_m3" or prop == {}


def test_godot_supervisor_includes_zb0_track() -> None:
    def fake_probe(task):  # noqa: ANN001
        return {"kind": "player_ia_probe", "ok": True, "online_count": 2, "checks": []}

    import team.godot_supervisor as gs

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(gs, "probe_player_ia", fake_probe)
    monkeypatch.setenv("LBG_TEAM_GODOT_SOE_M3", "0")
    monkeypatch.setenv("LBG_TEAM_GODOT_GATEWAY_SMOKE", "0")
    try:
        client = TestClient(app)
        created = client.post(
            "/v1/team/tasks",
            json={
                "role": "qa",
                "objective": "Supervise Godot zb0",
                "actor_id": "u:qa",
                "context": {"godot_supervisor": True, "godot_mode": "zb0"},
            },
        ).json()
        ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
        tracks = {t["track"] for t in ran["result"]["tracks"]}
        assert "zb0_readiness" in tracks
    finally:
        monkeypatch.undo()
