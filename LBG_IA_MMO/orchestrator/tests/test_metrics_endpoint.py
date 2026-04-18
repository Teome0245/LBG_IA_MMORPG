from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator.main import app


def test_metrics_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_METRICS_ENABLED", raising=False)
    monkeypatch.delenv("LBG_METRICS_TOKEN", raising=False)
    client = TestClient(app)
    assert client.get("/metrics").status_code == 404


def test_metrics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_METRICS_ENABLED", "1")
    monkeypatch.delenv("LBG_METRICS_TOKEN", raising=False)
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "lbg_process_uptime_seconds" in r.text
