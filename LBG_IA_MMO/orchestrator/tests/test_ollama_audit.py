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


def test_reason_forge_profile_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_REASON_MODEL_FORGE", raising=False)
    from team.reason_llm import reason_local_model

    assert reason_local_model(profile="forge") == "gemma4:e2b"
    assert reason_local_model(profile="pm") == "gemma4:26b"
