"""Seed versionné : `world/seed_data/world_initial.json` et repli."""

from __future__ import annotations

from pathlib import Path

import pytest

from world.seed import load_initial_world_state, resolve_seed_path
from world.state import WorldState


def test_default_seed_loads_two_npcs() -> None:
    w = load_initial_world_state()
    assert "npc:smith" in w.npcs
    assert "npc:merchant" in w.npcs
    assert w.npcs["npc:merchant"].role == "merchant"
    assert isinstance(w.npcs["npc:smith"].reputation_value, int)


def test_bootstrap_default_matches_seed() -> None:
    w = WorldState.bootstrap_default()
    assert len(w.npcs) >= 1
    assert "npc:smith" in w.npcs


def test_seed_fallback_when_file_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    monkeypatch.setenv("LBG_MMO_SEED_PATH", str(bad))
    caplog.set_level("WARNING")
    w = load_initial_world_state()
    assert "npc:smith" in w.npcs
    assert len(w.npcs) == 1
