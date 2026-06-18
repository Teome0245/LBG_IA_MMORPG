"""Cooldown social Lia — anti-spam greet/interact."""

from __future__ import annotations

import time

import pytest

from lbg_agents.core3_player_events import (
    greet_recently_sent,
    mark_proactive_action,
    maybe_apply_social_cooldown,
    proactive_suppressed,
    record_greet,
)
from lbg_agents.lia_orchestrator import build_proactive_prompt


@pytest.fixture
def state_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LBG_CORE3_LIA_PROACTIVE_COOLDOWN_S", "120")
    monkeypatch.setenv("LBG_CORE3_LIA_GREET_COOLDOWN_S", "300")


def test_maybe_apply_social_cooldown_after_interact_greet(state_dir) -> None:
    maybe_apply_social_cooldown(
        "lia",
        {
            "ok": True,
            "action": "interact",
            "line": "interact|Lia|tatooine|7|0|0|greet:Teome",
        },
    )
    assert proactive_suppressed("lia")
    assert greet_recently_sent("lia", "Teome")


def test_build_proactive_prompt_skips_greet_scene_when_recent(state_dir, monkeypatch) -> None:
    record_greet("lia", "Teome")
    monkeypatch.setattr("lbg_agents.lia_orchestrator.relay_players_online", lambda: ["Teome"])
    monkeypatch.setattr("lbg_agents.lia_orchestrator.fetch_brain_status", lambda: None)
    monkeypatch.setattr("lbg_agents.lia_orchestrator.proactive_tick_index", lambda: 0)
    prompt = build_proactive_prompt(tick_index=0)
    assert "greet:Teome" not in prompt
    assert "exploration" in prompt.lower() or "spectacle" in prompt.lower() or "presence" in prompt.lower()


def test_proactive_cooldown_expires(state_dir, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CORE3_LIA_PROACTIVE_COOLDOWN_S", "1")
    mark_proactive_action("lia", pause_s=0.05)
    assert proactive_suppressed("lia")
    time.sleep(0.06)
    assert not proactive_suppressed("lia")
