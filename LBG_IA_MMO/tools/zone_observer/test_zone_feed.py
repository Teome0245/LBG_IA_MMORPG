#!/usr/bin/env python3
"""Tests zone_feed (M1)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "tools" / "zone_observer"))
sys.path.insert(0, str(ROOT))

from zone_feed import (  # noqa: E402
    ZoneEntity,
    collect_entities,
    export_payload,
    format_table,
    pick_origin,
    sort_entities,
)

from godot_bridge import GodotBridge, entity_oid  # noqa: E402


class TestZoneFeed(unittest.TestCase):
    def test_collect_and_sort(self) -> None:
        os.environ["LBG_GATEWAY_TRACK_PLAYERS"] = "Teome,Lia"
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp)
            loc = ROOT / "content/core3/locations"
            (bridge / "player_snapshots.json").write_text(
                json.dumps(
                    {
                        "players": {
                            "Teome": {
                                "online": True,
                                "firstname": "Teome",
                                "x": 7.26,
                                "y": 1.15,
                                "z": -0.89,
                                "parent_id": 1082877,
                                "in_interior": True,
                                "zone": "tatooine",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (bridge / "npc_snapshots.json").write_text(
                json.dumps(
                    {
                        "lia": {
                            "display_name": "Lia",
                            "x": 3520.0,
                            "y": 0.0,
                            "z": -4800.0,
                            "zone": "tatooine",
                            "ts": 1_700_000_000.0,
                            "online": True,
                        }
                    }
                ),
                encoding="utf-8",
            )
            entities = collect_entities(bridge_dir=bridge, locations_dir=loc, max_age_s=99999)
            self.assertGreaterEqual(len(entities), 2)
            kinds = {e.kind for e in entities}
            self.assertIn("player", kinds)
            self.assertIn("npc", kinds)
            ox, oz = pick_origin(entities, None, None)
            sorted_e = sort_entities(entities, ox, oz)
            table = format_table(sorted_e, ox, oz)
            self.assertIn("Teome", table)
            self.assertIn("Lia", table)


class TestGodotBridge(unittest.TestCase):
    def test_entity_oid_stable(self) -> None:
        a = entity_oid("player:Teome")
        b = entity_oid("player:Teome")
        self.assertEqual(a, b)
        self.assertNotEqual(a, entity_oid("npc:lia"))

    def test_sync_spawn_and_move(self) -> None:
        bridge = GodotBridge(port=0)
        e = ZoneEntity("player:Teome", "player", "Teome", 100.0, 0.0, 200.0)
        self.assertTrue(bridge.sync_entity(e.id, e.kind, e.name, e.x, e.y, e.z))
        self.assertFalse(bridge.sync_entity(e.id, e.kind, e.name, e.x, e.y, e.z))
        self.assertTrue(bridge.sync_entity(e.id, e.kind, e.name, 101.0, 0.0, 200.0))
        bridge.close()


if __name__ == "__main__":
    unittest.main()
