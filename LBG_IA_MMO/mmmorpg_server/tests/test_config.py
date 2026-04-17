"""Constantes par défaut du module config."""

from __future__ import annotations

import unittest

import mmmorpg_server.config as cfg


class TestConfigDefaults(unittest.TestCase):
    def test_day_cycle_not_here(self):
        self.assertGreater(cfg.PORT, 0)
        self.assertGreater(cfg.TICK_RATE_HZ, 0)
        self.assertGreater(cfg.MAX_WS_INBOUND_BYTES, 1000)
        self.assertGreaterEqual(cfg.MOVE_MIN_INTERVAL_S, 0.0)


if __name__ == "__main__":
    unittest.main()
