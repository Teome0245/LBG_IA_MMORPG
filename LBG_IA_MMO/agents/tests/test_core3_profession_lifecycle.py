"""Tests cycles metier joueurs IA."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lbg_agents.core3_players import get_ai_player
from lbg_agents.core3_profession_lifecycle import (
    _advance_phase,
    pick_scene_index_for_lifecycle,
    save_state_registry,
    tick_player_lifecycle,
)


@pytest.fixture()
def lifecycle_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = {
        "version": 1,
        "real_hours": {
            "learning": 0.001,
            "mastery_practice": 0.001,
            "decay": 0.001,
            "transition": 0.001,
        },
        "mastery_threshold_pct": 50,
        "learning_progress_pct_per_tick": 60,
        "decay_progress_pct_per_tick": 30,
        "scene_focus_by_phase": {
            "learning": "primary",
            "mastery_practice": "primary",
            "secondary_learning": "secondary",
            "decay": "transition",
            "transition": "transition",
        },
        "profession_scene_tags": {
            "scout": ["forage", "search"],
            "entertainer": ["dance", "cantina_dance"],
        },
    }
    cfg_path = tmp_path / "lifecycle.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    state_path = tmp_path / "state.json"
    monkeypatch.setenv("LBG_CORE3_PROFESSION_LIFECYCLE_JSON", str(cfg_path))
    monkeypatch.setenv("LBG_CORE3_PLAYER_PROFESSION_STATE_JSON", str(state_path))
    save_state_registry({})
    return cfg_path, state_path


def test_tick_advances_through_phases(lifecycle_env):
    nix = get_ai_player("nix")
    view = tick_player_lifecycle(nix, activity=True)
    assert view.phase in {"learning", "mastery_practice", "secondary_learning", "decay", "transition"}
    assert view.focus_profession in {nix.profession_current, nix.profession_secondary}


def test_advance_phase_transition_swaps_primary():
    now = int(time.time())
    row = {
        "primary": "scout",
        "secondary": "marksman",
        "phase": "transition",
        "phase_started_at": now - 7200,
        "primary_mastery_pct": 10,
        "secondary_mastery_pct": 80,
        "cycle_index": 0,
        "forgotten": [],
    }
    cfg = {"real_hours": {"transition": 0.001}, "mastery_threshold_pct": 90}
    out = _advance_phase(row, cfg, now)
    assert out["primary"] == "marksman"
    assert out["phase"] == "learning"
    assert out["cycle_index"] == 1


def test_pick_scene_index_for_scout_focus(lifecycle_env):
    scenes = [{"id": "forage"}, {"id": "greet"}]
    cfg = json.loads(lifecycle_env[0].read_text(encoding="utf-8"))
    idx = pick_scene_index_for_lifecycle(
        scenes,
        base_index=1,
        focus_profession="scout",
        cfg=cfg,
    )
    assert scenes[idx]["id"] == "forage"
