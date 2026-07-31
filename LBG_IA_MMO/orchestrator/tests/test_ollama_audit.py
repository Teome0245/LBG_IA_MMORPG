"""Tests audit Ollama VM 110."""

from __future__ import annotations

import pytest

from team.ollama_audit import _model_available, audit_ollama_lan


def test_model_available_exact_and_prefix() -> None:
    installed = {"gemma4:26b", "gemma4:e2b"}
    assert _model_available("gemma4:26b", installed)
    assert not _model_available("phi4-mini:latest", installed)


def test_audit_live_or_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DIALOGUE_LLM_MODEL", "gemma4:26b")
    monkeypatch.setenv("LBG_REASON_MODEL_FORGE", "gemma4:e2b")
    monkeypatch.setenv("LBG_JOBS_PLANNER_LLM_MODEL", "gemma4:e2b")
    out = audit_ollama_lan()
    assert "track" in out
    if out.get("ok"):
        assert out["model_count"] >= 1
        assert not out.get("gaps")


def test_audit_skips_cloud_dialogue_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DIALOGUE_FAST_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LBG_COMPANION_LLM_MODEL", "gemma4:e2b")
    monkeypatch.setenv("LBG_COMPANION_LLM_BASE_URL", "http://192.168.0.110:11434/v1")
    out = audit_ollama_lan()
    assert "track" in out
    if out.get("installed"):
        assert not any("dialogue_fast" in g for g in out.get("gaps") or [])


def test_reason_forge_profile_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_REASON_MODEL_FORGE", raising=False)
    monkeypatch.delenv("LBG_REASON_MODEL_ROUTER", raising=False)
    monkeypatch.delenv("LBG_REASON_MODEL_JSON", raising=False)
    monkeypatch.delenv("LBG_REASON_MODEL_CODE", raising=False)
    from team.reason_llm import reason_local_model

    assert reason_local_model(profile="forge") == "gemma4:e2b"
    assert reason_local_model(profile="router") == "qwen2.5:3b"
    assert reason_local_model(profile="json") == "qwen2.5:3b"
    assert reason_local_model(profile="fast") == "llama3.2:3b"
    assert reason_local_model(profile="code") == "gemma4:26b"
    assert reason_local_model(profile="pm") == "gemma4:26b"
