"""Cycle jour / nuit (6 h simulées par défaut)."""

from __future__ import annotations

import unittest

from mmmorpg_server.world_core.time_manager import DAY_CYCLE_SECONDS, TimeManager


class TestTimeManager(unittest.TestCase):
    def test_day_fraction_wraps(self):
        tm = TimeManager(day_cycle_seconds=100.0)
        self.assertAlmostEqual(tm.day_fraction, 0.0)
        tm.advance(50.0)
        self.assertAlmostEqual(tm.day_fraction, 0.5)
        tm.advance(50.0)
        self.assertAlmostEqual(tm.day_fraction, 0.0)

    def test_plan_cycle_six_hours(self):
        self.assertEqual(DAY_CYCLE_SECONDS, 6 * 3600)


if __name__ == "__main__":
    unittest.main()
