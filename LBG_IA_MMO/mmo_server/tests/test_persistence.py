from pathlib import Path

from world.persistence import (
    load_world_state,
    save_world_state,
    world_state_from_dict,
    world_state_to_dict,
)
from world.state import WorldState


def test_roundtrip_dict() -> None:
    w = WorldState.bootstrap_default()
    w.now_s = 99.5
    w.npcs["npc:smith"].reputation_value = 12
    d = world_state_to_dict(w)
    w2 = world_state_from_dict(d)
    assert w2.now_s == 99.5
    assert "npc:smith" in w2.npcs
    assert "npc:merchant" in w2.npcs
    assert w2.npcs["npc:smith"].gauges.hunger == w.npcs["npc:smith"].gauges.hunger
    assert w2.npcs["npc:smith"].reputation_value == 12


def test_save_load_file(tmp_path: Path) -> None:
    w = WorldState.bootstrap_default()
    w.now_s = 12.0
    w.npcs["npc:smith"].gauges.hunger = 0.42
    path = tmp_path / "s.json"
    save_world_state(path, w)
    w2 = load_world_state(path)
    assert w2 is not None
    assert w2.now_s == 12.0
    assert abs(w2.npcs["npc:smith"].gauges.hunger - 0.42) < 1e-9


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_world_state(tmp_path / "nope.json") is None


def test_load_invalid_json_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{", encoding="utf-8")
    assert load_world_state(p) is None
