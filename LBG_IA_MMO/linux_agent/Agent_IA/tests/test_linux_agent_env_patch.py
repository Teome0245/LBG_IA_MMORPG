import unittest

import core as agent_mod


class TestLinuxEnvPatch(unittest.TestCase):
    def test_env_set_key_adds_or_replaces(self) -> None:
        original = "A=1\n#comment\nB=2\n"
        updated = agent_mod.env_set_key(original, "B", "9")
        self.assertIn("B=9", updated)
        updated2 = agent_mod.env_set_key(updated, "C", "3")
        self.assertIn("C=3", updated2)

