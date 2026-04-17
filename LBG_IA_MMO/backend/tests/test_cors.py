"""CORS pilot cross-origin — LBG_CORS_ORIGINS."""

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


def test_no_cors_without_lbg_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_CORS_ORIGINS", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz", headers={"Origin": "http://192.168.0.110"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers.keys()}


def test_cors_preflight_when_origins_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CORS_ORIGINS", "http://192.168.0.110")
    app = create_app()
    client = TestClient(app)
    r = client.options(
        "/healthz",
        headers={
            "Origin": "http://192.168.0.110",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://192.168.0.110"
