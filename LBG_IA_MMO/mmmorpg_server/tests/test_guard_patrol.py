"""Ronde des gardes (coordonnées seed + grille village)."""

from __future__ import annotations

import math
import unittest

from mmmorpg_server.game_state import GameState


class TestGuardPatrol(unittest.TestCase):
    def test_patrol_waypoints_follow_pixie_pois_when_locations_loaded(self) -> None:
        game = GameState()
        npc = game.get_npc("npc:guard")
        self.assertIsNotNone(npc)
        assert npc is not None
        pt = game._npc_guard_patrol_point_ids(npc)
        for loc_id in pt:
            self.assertTrue(
                any(isinstance(lo, dict) and str(lo.get("id", "")) == loc_id for lo in game.locations),
                f"jalon inexistant dans locations: {loc_id!r}",
            )

    def test_guard_moves_on_tick_with_default_world(self) -> None:
        game = GameState()
        npc = game.get_npc("npc:guard")
        self.assertIsNotNone(npc)
        assert npc is not None

        npc.busy_timer = 0.0
        x0, z0 = float(npc.x), float(npc.z)

        for _ in range(2200):
            game.tick(0.025)

        dist = math.hypot(float(npc.x) - x0, float(npc.z) - z0)
        self.assertGreater(
            dist,
            1.5,
            msg="gardien immobile après une simulation courte : ronde / chemin / buts monde à vérifier",
        )


if __name__ == "__main__":
    unittest.main()
