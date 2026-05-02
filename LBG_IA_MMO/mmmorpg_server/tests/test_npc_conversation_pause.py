"""Immobilisation PNJ pendant une conversation."""

from __future__ import annotations

import math
import unittest

from mmmorpg_server.game_state import GameState, NPC_CONVERSATION_RESUME_DELAY_S


class TestNpcConversationPause(unittest.TestCase):
    def test_freeze_npc_faces_player_and_resumes_after_delay(self) -> None:
        game = GameState()
        player = game.add_player("DialogueTester")
        npc = game.get_npc("npc:merchant")
        self.assertIsNotNone(npc)
        assert npc is not None

        player.x = npc.x + 10.0
        player.z = npc.z
        npc.vx = 3.0
        npc.vz = -2.0

        game.freeze_npc_and_face("npc:merchant", player.id)

        self.assertAlmostEqual(npc.busy_timer, NPC_CONVERSATION_RESUME_DELAY_S)
        self.assertAlmostEqual(npc.ry, math.atan2(player.x - npc.x, player.z - npc.z))
        self.assertEqual((npc.vx, npc.vy, npc.vz), (0.0, 0.0, 0.0))

        game.tick(1.0)
        self.assertAlmostEqual(npc.busy_timer, NPC_CONVERSATION_RESUME_DELAY_S - 1.0)
        self.assertEqual((npc.vx, npc.vy, npc.vz), (0.0, 0.0, 0.0))

        game.tick(NPC_CONVERSATION_RESUME_DELAY_S)
        self.assertLessEqual(npc.busy_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
