"""Inventaire joueur v1 — session WS (stats.inventory)."""

from __future__ import annotations

import unittest

from mmmorpg_server.game_state import GameState


class TestPlayerInventory(unittest.TestCase):
    def test_add_player_seeds_inventory(self) -> None:
        game = GameState()
        p = game.add_player("Tester")
        inv = (p.stats or {}).get("inventory")
        self.assertIsInstance(inv, list)
        assert isinstance(inv, list)
        self.assertGreaterEqual(len(inv), 1)
        first = inv[0]
        self.assertIsInstance(first, dict)
        self.assertIn("item_id", first)
        self.assertIn("qty", first)

    def test_first_move_merges_stats_without_wiping_inventory(self) -> None:
        game = GameState()
        p = game.add_player("Hero")
        inv0 = list((p.stats or {}).get("inventory") or [])
        game.apply_player_move(p.id, 1.0, 0.0, 0.0)
        p2 = game.entities[p.id]
        inv1 = (p2.stats or {}).get("inventory")
        self.assertIsInstance(inv1, list)
        self.assertEqual(len(inv1), len(inv0))
        self.assertIn("hp", p2.stats or {})
        self.assertEqual((p2.stats or {}).get("hp"), 100)

    def test_commit_inventory_requires_player_id(self) -> None:
        game = GameState()
        ok, reason = game.commit_dialogue(
            npc_id="npc:merchant",
            trace_id="inv-reject-1",
            flags={"player_item_id": "item:test", "player_item_qty_delta": 2},
            player_id=None,
        )
        self.assertFalse(ok)
        self.assertIn("player_id", reason)

    def test_commit_inventory_applies_to_player(self) -> None:
        game = GameState()
        p = game.add_player("Loot")
        ok, reason = game.commit_dialogue(
            npc_id="npc:merchant",
            trace_id="inv-ok-1",
            flags={
                "player_item_id": "item:gift",
                "player_item_qty_delta": 1,
                "player_item_label": "Cadeau du marchand",
            },
            player_id=p.id,
        )
        self.assertTrue(ok, reason)
        inv = (game.entities[p.id].stats or {}).get("inventory")
        self.assertIsInstance(inv, list)
        gift = next((x for x in inv if isinstance(x, dict) and x.get("item_id") == "item:gift"), None)
        self.assertIsNotNone(gift)
        assert isinstance(gift, dict)
        self.assertEqual(gift.get("qty"), 1)
        self.assertEqual(gift.get("label"), "Cadeau du marchand")


if __name__ == "__main__":
    unittest.main()
