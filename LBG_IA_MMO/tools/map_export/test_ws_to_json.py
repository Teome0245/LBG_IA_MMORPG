#!/usr/bin/env python3
"""Tests M4.4 ws_to_json (filtre Mos Eisley)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "map_export"))

from ws_to_json import filter_mos_eisley  # noqa: E402


class TestWsToJson(unittest.TestCase):
    def test_filter_mos_eisley(self) -> None:
        objs = [
            {"x": 3520, "z": -4800},
            {"x": 6000, "z": -1000},
            {"x": 3510, "z": -4790},
        ]
        out = filter_mos_eisley(objs, radius=200.0)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
