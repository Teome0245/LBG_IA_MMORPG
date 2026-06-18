"""Tests élévation agentique Chat → job (point 6, inspiré P03)."""

from __future__ import annotations

import pytest

from router.agentic import chat_agentic_enabled, elevate_to_job, should_elevate_to_agentic


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_CHAT_AGENTIC", raising=False)
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    assert chat_agentic_enabled({}) is False
    assert should_elevate_to_agentic("devops_probe", {}) is False


def test_context_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CHAT_AGENTIC", "1")
    assert chat_agentic_enabled({"prefer_agentic": False}) is False
    assert chat_agentic_enabled({"prefer_agentic": True}) is True


def test_elevation_requires_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CHAT_AGENTIC", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "0")
    assert should_elevate_to_agentic("devops_probe", {}) is False
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    assert should_elevate_to_agentic("devops_probe", {}) is True


def test_only_actionable_intents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CHAT_AGENTIC", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    assert should_elevate_to_agentic("devops_probe", {}) is True
    assert should_elevate_to_agentic("npc_dialogue", {}) is False
    assert should_elevate_to_agentic("unknown", {}) is False


def test_no_elevation_with_structured_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CHAT_AGENTIC", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    # Action structurée explicite (console DevOps) : on ne ré-planifie pas depuis le texte.
    assert should_elevate_to_agentic("devops_probe", {"devops_action": {"kind": "ssh_run"}}) is False
    assert should_elevate_to_agentic("devops_probe", {"prefer_agentic": True, "devops_action": {"kind": "selfcheck"}}) is False
    assert should_elevate_to_agentic("desktop_control", {"desktop_action": {"kind": "open_app"}}) is False


def test_elevate_to_job_creates_background_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CHAT_AGENTIC", "1")
    monkeypatch.setenv("LBG_JOBS_RUNNER_ENABLED", "1")
    out = elevate_to_job(
        text="sonde devops complète de la stack",
        actor_id="pilot:1",
        intent="devops_probe",
        context={"devops_dry_run": True},
    )
    assert out["agentic"] is True
    assert out["elevated_from"] == "devops_probe"
    assert isinstance(out["job_id"], str) and out["job_id"]
    assert "arrière-plan" in out["reply"]
