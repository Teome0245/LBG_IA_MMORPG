"""Garde-fous taille / encodage des frames WebSocket entrantes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mmmorpg_server.game_state import GameState
from mmmorpg_server.main import (
    _dialogue_commit_world_event,
    _extract_ia_dialogue_commit,
    _format_ia_placeholder,
    _inbound_to_utf8,
)
from mmmorpg_server.protocol import msg_world_tick


class TestWsInbound(unittest.TestCase):
    def test_accepts_short_str(self):
        text, err = _inbound_to_utf8('{"type":"hello"}')
        self.assertIsNone(err)
        self.assertEqual(text, '{"type":"hello"}')

    def test_rejects_oversize_bytes(self):
        with patch("mmmorpg_server.main.config.MAX_WS_INBOUND_BYTES", 8):
            text, err = _inbound_to_utf8(b"123456789")
            self.assertIsNone(text)
            self.assertIn("volumineux", err or "")

    def test_rejects_bad_utf8(self):
        with patch("mmmorpg_server.main.config.MAX_WS_INBOUND_BYTES", 100):
            text, err = _inbound_to_utf8(b"\xff\xfe")
            self.assertIsNone(text)
            self.assertIn("UTF-8", err or "")

    def test_placeholder_uses_npc_name(self):
        out = _format_ia_placeholder(
            "…un instant. (Le PNJ vous regarde, comme s’il réfléchissait.)",
            "Garde",
        )
        self.assertIn("Garde vous regarde", out)
        self.assertNotIn("Le PNJ", out)

    def test_extract_ia_dialogue_commit_from_output(self):
        payload = {
            "result": {
                "output": {
                    "commit": {
                        "npc_id": "npc:merchant",
                        "flags": {"aid_hunger_delta": -0.2, "aid_reputation_delta": 5},
                    }
                }
            }
        }

        commit, err = _extract_ia_dialogue_commit(payload, target_npc_id="npc:merchant")

        self.assertIsNone(err)
        self.assertEqual(commit, payload["result"]["output"]["commit"])

    def test_extract_ia_dialogue_commit_uses_target_when_npc_missing(self):
        payload = {"result": {"output": {"remote": {"commit": {"flags": {"quest_id": "q:starter"}}}}}}

        commit, err = _extract_ia_dialogue_commit(payload, target_npc_id="npc:guard")

        self.assertIsNone(err)
        self.assertEqual(commit, {"npc_id": "npc:guard", "flags": {"quest_id": "q:starter"}})

    def test_extract_ia_dialogue_commit_rejects_other_npc(self):
        payload = {
            "result": {
                "output": {
                    "commit": {
                        "npc_id": "npc:mayor",
                        "flags": {"reputation_delta": 10},
                    }
                }
            }
        }

        commit, err = _extract_ia_dialogue_commit(payload, target_npc_id="npc:guard")

        self.assertIsNone(commit)
        self.assertIn("mismatch", err or "")

    def test_extracted_ia_dialogue_commit_updates_game_state(self):
        game = GameState()
        before = game.get_npc_gauges("npc:merchant")
        payload = {
            "result": {
                "output": {
                    "commit": {
                        "npc_id": "npc:merchant",
                        "flags": {
                            "aid_hunger_delta": 0.4,
                            "aid_thirst_delta": 0.2,
                            "aid_fatigue_delta": 0.1,
                            "aid_reputation_delta": 7,
                        },
                    }
                }
            }
        }

        commit, err = _extract_ia_dialogue_commit(payload, target_npc_id="npc:merchant")
        self.assertIsNone(err)
        assert commit is not None
        ok, reason = game.commit_dialogue(
            npc_id=commit["npc_id"],
            trace_id="ia-dialogue-action-1",
            flags=commit.get("flags"),
        )

        after = game.get_npc_gauges("npc:merchant")
        self.assertTrue(ok, reason)
        self.assertGreater(after["hunger"], before["hunger"])
        self.assertGreater(after["thirst"], before["thirst"])
        self.assertGreater(after["fatigue"], before["fatigue"])
        self.assertEqual(game.get_npc_reputation("npc:merchant"), 7)

    def test_npc_snapshot_exposes_world_state(self):
        game = GameState()
        ok, reason = game.commit_dialogue(
            npc_id="npc:merchant",
            trace_id="snapshot-world-state-1",
            flags={"aid_hunger_delta": 0.3, "aid_reputation_delta": 4, "quest_id": "q:test"},
        )
        self.assertTrue(ok, reason)

        snap = next(e for e in game.entity_snapshots() if e["id"] == "npc:merchant")
        state = snap.get("world_state")

        self.assertIsInstance(state, dict)
        assert isinstance(state, dict)
        self.assertEqual(state["reputation"], 4)
        self.assertIn("hunger", state["gauges"])
        self.assertEqual(state["flags"]["quest_id"], "q:test")

    def test_dialogue_commit_world_event_is_sent_on_world_tick(self):
        commit = {
            "npc_id": "npc:merchant",
            "flags": {"aid_hunger_delta": -0.2, "aid_reputation_delta": 5},
        }
        event = _dialogue_commit_world_event(commit=commit, trace_id="trace-aid-1", reason="accepted")

        msg = msg_world_tick(
            world_time_s=12.0,
            day_fraction=0.5,
            entities=[],
            npc_reply="D'accord.",
            trace_id="trace-aid-1",
            world_event=event,
        )

        self.assertEqual(msg["world_event"]["type"], "dialogue_commit")
        self.assertEqual(msg["world_event"]["npc_id"], "npc:merchant")
        self.assertEqual(msg["world_event"]["trace_id"], "trace-aid-1")
        self.assertIn("Aide", msg["world_event"]["summary"])

    def test_dialogue_commit_world_event_quest_completed_summary(self):
        commit = {
            "npc_id": "npc:merchant",
            "flags": {"quest_id": "q:fin", "quest_step": 2, "quest_accepted": True, "quest_completed": True},
        }
        event = _dialogue_commit_world_event(commit=commit, trace_id="t1", reason="accepted")
        self.assertIn("accomplie", event["summary"].lower())
        self.assertIn("q:fin", event["summary"])

    def test_npc_snapshot_exposes_quest_completed(self):
        game = GameState()
        ok, reason = game.commit_dialogue(
            npc_id="npc:merchant",
            trace_id="quest-done-1",
            flags={"quest_id": "q:fin", "quest_step": 1, "quest_completed": True},
        )
        self.assertTrue(ok, reason)
        snap = next(e for e in game.entity_snapshots() if e["id"] == "npc:merchant")
        self.assertTrue(snap["world_state"]["flags"].get("quest_completed"))

    def test_quest_commit_with_reputation_delta_updates_npc(self):
        game = GameState()
        self.assertEqual(game.get_npc_reputation("npc:merchant"), 0)
        ok, reason = game.commit_dialogue(
            npc_id="npc:merchant",
            trace_id="quest-rep-1",
            flags={
                "quest_id": "q:pay",
                "quest_step": 2,
                "quest_completed": True,
                "reputation_delta": 9,
            },
        )
        self.assertTrue(ok, reason)
        self.assertEqual(game.get_npc_reputation("npc:merchant"), 9)


if __name__ == "__main__":
    unittest.main()
