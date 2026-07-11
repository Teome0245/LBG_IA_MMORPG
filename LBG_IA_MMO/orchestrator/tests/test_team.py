"""Tests équipe virtuelle studio (phase A)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
os.environ.setdefault("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz,http://127.0.0.1:8000/healthz")

from orchestrator.main import app  # noqa: E402
from team import roles as team_roles  # noqa: E402
from team import store as team_store  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_team_db() -> None:
    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(None)


def test_team_plan_proposes_roles() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "valide le LAN et fais un brief PM", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    proposals = r.json()["proposals"]
    roles = {p["role"] for p in proposals}
    assert "qa" in roles
    assert "pm" in roles


def test_team_create_list_get() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/tasks",
        json={"role": "pm", "objective": "roadmap phase A", "actor_id": "u:1"},
    )
    assert r.status_code == 200
    task = r.json()
    assert task["status"] == "queued"
    assert task["role"] == "pm"

    r2 = client.get("/v1/team/tasks", params={"actor_id": "u:1"})
    assert r2.status_code == 200
    assert len(r2.json()["tasks"]) == 1

    r3 = client.get(f"/v1/team/tasks/{task['id']}")
    assert r3.status_code == 200
    assert r3.json()["objective"] == "roadmap phase A"


def test_team_run_pm_with_fake_dispatch() -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to, "brief": "jalons OK"}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={"role": "pm", "objective": "état du projet", "actor_id": "u:run"},
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "pm_brief"


def test_team_run_dev_game_with_fake_dispatch() -> None:
    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": True, "agent": routed_to, "brief": "correctif proposé"}

    team_roles.set_dispatch_for_tests(fake_dispatch)
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "dev_game",
            "objective": "analyser bug gameplay",
            "actor_id": "u:dev",
            "context": {"qa_failure_summary": {"smoke_ok": False}},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "dev_game_brief"


def test_team_plan_includes_dev_game() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/team/plan",
        json={"objective": "corriger le bug gameplay core3", "actor_id": "u:plan"},
    )
    assert r.status_code == 200
    roles = {p["role"] for p in r.json()["proposals"]}
    assert "dev_game" in roles


def test_team_run_qa_health_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200
        text = '{"status":"ok"}'

    class _Client:
        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            return _Resp()

    import lbg_agents.devops_executor as de

    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Client())

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={"role": "qa", "objective": "smoke healthz", "actor_id": "u:qa"},
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "qa_smoke"
    assert ran["result"]["ok"] is True


def test_team_approval_gate() -> None:
    monkeypatch_token = pytest.MonkeyPatch()
    monkeypatch_token.setenv("LBG_TEAM_APPROVAL_TOKEN", "secret-team")
    try:
        client = TestClient(app)
        created = client.post(
            "/v1/team/tasks",
            json={
                "role": "ops",
                "objective": "restart service",
                "approval_required": True,
                "actor_id": "u:ap",
            },
        ).json()
        blocked = client.post(f"/v1/team/tasks/{created['id']}/run").json()
        assert blocked["status"] == "review"

        bad = client.post(
            f"/v1/team/tasks/{created['id']}/approve",
            json={"token": "wrong"},
        ).json()
        assert bad.get("result", {}).get("approval_error") == "token invalide"

        ok = client.post(
            f"/v1/team/tasks/{created['id']}/approve",
            json={"token": "secret-team"},
        ).json()
        assert ok["status"] == "queued"
    finally:
        monkeypatch_token.undo()


def test_team_cancel() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={"role": "qa", "objective": "à annuler", "actor_id": "u:cancel"},
    ).json()
    cancelled = client.post(f"/v1/team/tasks/{created['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"


def test_team_ops_storage_context(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "ops",
            "objective": "sonde stockage",
            "actor_id": "u:ops",
            "context": {
                "ops_kind": "proxmox_storage",
                "proxmox_storage": {"ok": True, "outcome": "warn", "data_percent": 90},
            },
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "ops_storage"
    assert ran["result"]["ok"] is True


def test_team_ops_ollama_context(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "gemma4:26b"}]}

    class _Client:
        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "Client", lambda **kw: _Client())
    monkeypatch.setattr(httpx, "get", lambda url, timeout=8: _Resp())

    client = TestClient(app)
    created = client.post(
        "/v1/team/tasks",
        json={
            "role": "ops",
            "objective": "sonde ollama",
            "actor_id": "u:ops",
            "context": {"ops_kind": "ollama", "ollama_tags_url": "http://127.0.0.1:11434/api/tags"},
        },
    ).json()
    ran = client.post(f"/v1/team/tasks/{created['id']}/run").json()
    assert ran["status"] == "done"
    assert ran["result"]["kind"] == "ops_ollama"
    assert ran["result"]["ok"] is True
