from __future__ import annotations

from pathlib import Path

from mmmorpg_server.persistence import load_state, save_state


def test_save_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "mmmorpg_state.json"
    seen = {"t1", "t2"}
    flags = {"npc:merchant": {"quest_accepted": True, "quest_id": "q1"}}
    rep = {"npc:merchant": 7}
    save_state(p, seen_trace_ids=seen, npc_flags=flags, npc_reputation=rep)
    loaded = load_state(p)
    assert loaded is not None
    seen2, flags2, rep2 = loaded
    assert "t1" in seen2 and "t2" in seen2
    assert flags2["npc:merchant"]["quest_accepted"] is True
    assert rep2["npc:merchant"] == 7


def test_load_missing_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    assert load_state(p) is None

