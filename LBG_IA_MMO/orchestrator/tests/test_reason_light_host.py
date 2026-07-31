"""Tests routage REASON light (111) vs heavy (110)."""

from __future__ import annotations

import pytest

from team.reason_llm import (
    reason_local_base_url,
    reason_local_model,
    reason_routes,
)


@pytest.fixture(autouse=True)
def _clear_reason_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("LBG_REASON_") or key in ("OLLAMA_BASE_URL",):
            monkeypatch.delenv(key, raising=False)


def test_router_uses_light_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_REASON_LOCAL_BASE_URL", "http://192.168.0.110:11434")
    monkeypatch.setenv("LBG_REASON_LIGHT_BASE_URL", "http://192.168.0.111:11434")
    monkeypatch.setenv("LBG_REASON_MODEL_ROUTER", "qwen2.5:3b")
    monkeypatch.setenv("LBG_REASON_MODEL_CODE", "gemma4:26b")
    assert reason_local_base_url(profile="router") == "http://192.168.0.111:11434"
    assert reason_local_base_url(profile="json") == "http://192.168.0.111:11434"
    assert reason_local_base_url(profile="code") == "http://192.168.0.110:11434"
    assert reason_local_model(profile="router") == "qwen2.5:3b"


def test_router_routes_include_heavy_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_REASON_LOCAL_BASE_URL", "http://192.168.0.110:11434")
    monkeypatch.setenv("LBG_REASON_LIGHT_BASE_URL", "http://192.168.0.111:11434")
    monkeypatch.setenv("LBG_REASON_MODEL_ROUTER", "qwen2.5:3b")
    monkeypatch.setenv("LBG_REASON_LIGHT_FAILOVER_HEAVY", "1")
    monkeypatch.setenv("LBG_REASON_MODEL_FORGE", "gemma4:e2b")
    routes = reason_routes(profile="router")
    locals_ = [r for r in routes if r["tier"] == "local"]
    assert len(locals_) >= 2
    assert locals_[0]["base_url"] == "http://192.168.0.111:11434"
    assert locals_[0]["model"] == "qwen2.5:3b"
    assert locals_[1]["base_url"] == "http://192.168.0.110:11434"
    assert locals_[1]["host"] == "heavy_failover"


def test_without_light_url_all_on_heavy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_REASON_LOCAL_BASE_URL", "http://192.168.0.110:11434")
    monkeypatch.setenv("LBG_REASON_MODEL_ROUTER", "gemma4:e2b")
    assert reason_local_base_url(profile="router") == "http://192.168.0.110:11434"
    routes = reason_routes(profile="router")
    locals_ = [r for r in routes if r["tier"] == "local"]
    assert len(locals_) == 1
