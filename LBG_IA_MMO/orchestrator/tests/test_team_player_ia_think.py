"""Tests think/tick player_ia L2."""

from __future__ import annotations

import os

import pytest

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402
from team.player_ia_think import infer_approval_on_create, resolve_player_ia_mode  # noqa: E402


@pytest.fixture(autouse=True)
def _reset() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_infer_approval_on_think_objective() -> None:
    assert infer_approval_on_create("player_ia", "Tour autonomie Lia think tick", {}) is True
    assert infer_approval_on_create("player_ia", "Sonde sidecar Prime", {}) is None


def test_player_ia_think_requires_l2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_APPROVAL_TOKEN", "think-secret")
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "player_ia",
            "objective": "Tick autonomie Nix sur Prime",
            "actor_id": "u:think",
            "context": {"player_id": "nix"},
        },
    ).json()
    assert created["approval_required"] is True
    blocked = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert blocked["status"] == "review"


def test_player_ia_think_runs_after_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_TEAM_APPROVAL_TOKEN", "think-secret")

    def fake_tick(player_id, *, via=None):  # noqa: ANN001
        return {"ok": True, "outcome": "thought", "player_id": player_id}

    monkeypatch.setattr("lbg_agents.core3_player_autonomy.player_autonomy_tick", fake_tick)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "player_ia",
            "objective": "think tick lia",
            "actor_id": "u:think",
            "context": {"player_ia_mode": "think_tick", "player_id": "lia"},
        },
    ).json()
    client.post(f"/v1/team/tasks/{created['id']}/approve", json={"token": "think-secret"})
    ran = client.post(
        f"/v1/team/tasks/{created['id']}/run",
        json={"approval_token": "think-secret"},
    ).json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "player_ia_think"
    assert ran["result"]["player_id"] == "lia"


def test_team_meta_lists_aliases() -> None:
    client = TestClient(app)
    r = client.get("/v1/team/meta")
    assert r.status_code == 200
    data = r.json()
    assert len(data["roles"]) >= 5
    ops = next(x for x in data["roles"] if x["role"] == "ops")
    assert ops["alias"] == "Héphaïstos"
    assert any(sp["id"] == "client_godot" for sp in data["subprojects"])
