"""Tests conversion coords cellule → monde."""

from __future__ import annotations

import unittest
from pathlib import Path

from services.lbg_gateway.world_coords import (
    cell_to_world,
    is_cell_local_pos,
    load_location_anchors,
    resolve_world_pos,
)

ROOT = Path(__file__).resolve().parents[3]
LOC = ROOT / "content/core3/locations"


class TestWorldCoords(unittest.TestCase):
    def test_barman_post_near_anchor(self) -> None:
        anchors = load_location_anchors(str(LOC))
        bar = anchors["mos_eisley_cantina_bar"]
        world = cell_to_world({"x": 7.26, "y": 1.15, "z": -0.89}, bar)
        self.assertGreater(world[0], 3400.0)
        self.assertLess(world[2], -4700.0)

    def test_resolve_local_post(self) -> None:
        anchors = load_location_anchors(str(LOC))
        pos = resolve_world_pos(
            {"x": 7.26, "y": 1.15, "z": -0.89},
            location_id="mos_eisley_cantina_bar",
            anchors=anchors,
        )
        self.assertTrue(is_cell_local_pos(7.26, 1.15, -0.89))
        self.assertFalse(is_cell_local_pos(3526.0, 5.0, -4799.0))
        self.assertAlmostEqual(pos[0], 3446.26, places=1)

    def test_training_post_uses_cell_anchor(self) -> None:
        anchors = load_location_anchors(str(LOC))
        pos = resolve_world_pos(
            {"x": 14.035821914673, "y": -13.745964050293, "z": 1.133056640625},
            location_id="",
            anchors=anchors,
            cell=1189637,
        )
        self.assertGreater(pos[0], 3450.0)
        self.assertLess(pos[0], 3490.0)
        self.assertGreater(pos[2], -4700.0)
        self.assertLess(pos[2], -4650.0)


if __name__ == "__main__":
    unittest.main()
