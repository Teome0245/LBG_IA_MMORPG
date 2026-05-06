from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import lbg_agents.devops_executor as de


def test_route_devops_context_forces_probe(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Client())

    from orchestrator.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "ops:1",
            "text": "Ignoré si devops_action présent",
            "context": {
                "npc_name": "PNJ fantôme",
                "devops_action": {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "devops_probe"
    assert data["routed_to"] == "agent.devops"
    out = data["output"]
    assert out["capability"] == "devops_probe"
    assert out["policy"]["decision"] == "safe_read"
    assert out.get("agent") == "devops_executor"
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True


def test_route_devops_text_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> MagicMock:
            r = MagicMock()
            r.status_code = 200
            r.text = "ok"
            return r

    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Client())

    from orchestrator.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={"actor_id": "ops:1", "text": "sonde devops", "context": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "devops_probe"
    assert data["output"]["policy"]["decision"] == "safe_read"
    assert data["output"].get("agent") == "devops_executor"


def test_route_devops_sensitive_log_tail_requires_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)

    from orchestrator.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "ops:1",
            "text": "Ignoré si devops_action présent",
            "context": {"devops_action": {"kind": "read_log_tail", "path": "/var/log/syslog"}},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "devops_probe"
    out = data["output"]
    assert out["capability"] == "devops_probe"
    assert out["outcome"] == "approval_required"
    assert out["policy"]["decision"] == "approval_required"
    assert "agent" not in out


def test_route_devops_sensitive_log_tail_with_approval_reaches_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_LOG_ALLOWLIST", "/var/log/syslog")

    from orchestrator.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/route",
        json={
            "actor_id": "ops:1",
            "text": "Ignoré si devops_action présent",
            "context": {
                "devops_approval": "ok-local-policy",
                "devops_action": {"kind": "read_log_tail", "path": "/var/log/syslog"},
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    out = data["output"]
    assert out["policy"]["decision"] == "approved_action"
    assert out.get("agent") == "devops_executor"
