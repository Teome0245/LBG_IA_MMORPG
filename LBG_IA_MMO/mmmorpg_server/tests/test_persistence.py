from __future__ import annotations

from pathlib import Path

from mmmorpg_server.game_state import GameState
from mmmorpg_server.main import _persist_game_state
from mmmorpg_server.persistence import load_state, save_state


def test_save_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "mmmorpg_state.json"
    seen = {"t1", "t2"}
    flags = {"npc:merchant": {"quest_accepted": True, "quest_id": "q1"}}
    rep = {"npc:merchant": 7}
    gauges = {"npc:merchant": {"hunger": 0.2, "thirst": 0.3, "fatigue": 0.4}}
    save_state(p, seen_trace_ids=seen, npc_flags=flags, npc_reputation=rep, npc_gauges=gauges)
    loaded = load_state(p)
    assert loaded is not None
    seen2, flags2, rep2, gauges2 = loaded
    assert "t1" in seen2 and "t2" in seen2
    assert flags2["npc:merchant"]["quest_accepted"] is True
    assert rep2["npc:merchant"] == 7
    assert gauges2["npc:merchant"]["hunger"] == 0.2


def test_load_missing_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    assert load_state(p) is None


def test_persist_game_state_after_dialogue_commit(tmp_path: Path) -> None:
    p = tmp_path / "mmmorpg_state.json"
    game = GameState()
    ok, reason = game.commit_dialogue(
        npc_id="npc:merchant",
        trace_id="persist-immediate-1",
        flags={
            "quest_accepted": True,
            "quest_id": "q:persist",
            "aid_hunger_delta": 0.25,
            "aid_reputation_delta": 3,
        },
    )
    assert ok, reason

    assert _persist_game_state(game, str(p), source="test")

    loaded = load_state(p)
    assert loaded is not None
    seen, flags, rep, gauges = loaded
    assert "persist-immediate-1" in seen
    assert flags["npc:merchant"]["quest_id"] == "q:persist"
    assert rep["npc:merchant"] == 3
    assert gauges["npc:merchant"]["hunger"] == 0.25

