"""Sanitisation ia_context.session_summary."""

from __future__ import annotations

from mmmorpg_server.ia_context_sanitize import (
    SESSION_SUMMARY_KEYS,
    build_server_session_summary_parts,
    merge_session_summaries,
    sanitize_session_summary,
)


def test_sanitize_session_summary_accepts_whitelist() -> None:
    out = sanitize_session_summary(
        {
            "tracked_quest": "q1",
            "last_npc": "Mara",
            "player_note": "  hello  ",
            "session_mood": "calme",
            "evil": "x",
        }
    )
    assert out is not None
    assert "evil" not in out
    assert out["tracked_quest"] == "q1"
    assert out["last_npc"] == "Mara"
    assert out["player_note"] == "hello"


def test_sanitize_truncates_long_string() -> None:
    long_s = "a" * 200
    out = sanitize_session_summary({"tracked_quest": long_s})
    assert out is not None
    assert len(out["tracked_quest"]) == 160


def test_sanitize_rejects_empty() -> None:
    assert sanitize_session_summary({}) is None
    assert sanitize_session_summary(None) is None


def test_keys_frozenset() -> None:
    assert "tracked_quest" in SESSION_SUMMARY_KEYS
    assert "quest_snapshot" in SESSION_SUMMARY_KEYS
    assert "memory_hint" in SESSION_SUMMARY_KEYS


def test_build_server_session_summary_parts() -> None:
    parts = build_server_session_summary_parts(
        quest_state={"quest_id": "q:foo", "quest_step": 2, "status": "open"},
        npc_id="npc:a",
        npc_name="Mara",
    )
    assert parts["last_npc"] == "Mara"
    assert "q:foo" in parts["tracked_quest"]
    assert "step=2" in parts["quest_snapshot"]


def test_build_server_session_summary_parts_memory_hint_from_flags() -> None:
    parts = build_server_session_summary_parts(
        quest_state=None,
        npc_id="npc:x",
        npc_name=None,
        npc_flags={"reputation_delta": 1, "aid_hunger": 0.5},
    )
    assert "memory_hint" in parts
    assert "aid_hunger" in parts["memory_hint"]
    assert "reputation_delta" in parts["memory_hint"]


def test_merge_session_summaries_server_wins_memory_hint() -> None:
    server = build_server_session_summary_parts(
        quest_state=None,
        npc_id="npc:x",
        npc_name="Zed",
        npc_flags={"flag_a": 1},
    )
    merged = merge_session_summaries(
        server_parts=server,
        client_raw={"memory_hint": "client-should-not-win", "player_note": "hi"},
    )
    assert merged is not None
    assert "flag_a" in (merged.get("memory_hint") or "")
    assert merged.get("player_note") == "hi"


def test_merge_session_summaries_server_wins_tracked() -> None:
    server = build_server_session_summary_parts(
        quest_state={"quest_id": "q:server", "quest_step": 1},
        npc_id="npc:x",
        npc_name="Bob",
    )
    merged = merge_session_summaries(
        server_parts=server,
        client_raw={"tracked_quest": "client-wrong", "player_note": "hello"},
    )
    assert merged is not None
    assert "q:server" in (merged.get("tracked_quest") or "")
    assert merged.get("player_note") == "hello"
