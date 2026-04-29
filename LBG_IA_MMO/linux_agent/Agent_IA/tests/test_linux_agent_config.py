import unittest

import core as agent_mod


class TestLinuxAgentConfig(unittest.TestCase):
    def setUp(self) -> None:
        # Isoler le cache
        agent_mod.CFG_CACHE["mtime"] = None
        agent_mod.CFG_CACHE["vars"] = {}

    def test_host_matches_domain(self) -> None:
        self.assertTrue(agent_mod.host_matches("www.google.com", "google.com"))
        self.assertTrue(agent_mod.host_matches("google.com", "google.com"))
        self.assertFalse(agent_mod.host_matches("evilgoogle.com", "google.com"))

    def test_host_matches_wildcard(self) -> None:
        self.assertTrue(agent_mod.host_matches("a.example.org", "*.example.org"))
        self.assertFalse(agent_mod.host_matches("example.org", "*.example.org"))

