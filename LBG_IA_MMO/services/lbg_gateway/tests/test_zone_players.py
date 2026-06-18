"""Tests lecture joueurs zone (player_snapshots.json)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.lbg_gateway.zone_players import build_zone_player_entities

ROOT = Path(__file__).resolve().parents[3]
LOC = ROOT / "content/core3/locations"


class TestZonePlayers(unittest.TestCase):
    def test_online_teome_in_cantina(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap_path = Path(tmp) / "player_snapshots.json"
            snap_path.write_text(
                json.dumps(
                    {
                        "ts": 1,
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
                            },
                            "Lia": {
                                "online": True,
                                "firstname": "Lia",
                                "x": 7.26,
                                "y": 0.35,
                                "z": 0.91,
                                "parent_id": 1082877,
                                "in_interior": True,
                                "zone": "tatooine",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            ents = build_zone_player_entities(snapshots_path=snap_path, locations_dir=str(LOC))
            self.assertEqual(len(ents), 2)
            by_id = {e["id"]: e for e in ents}
            self.assertIn("player:Teome", by_id)
            self.assertIn("player:Lia", by_id)
            self.assertEqual(by_id["player:Teome"]["source"], "core3")
            self.assertGreater(by_id["player:Teome"]["pos"][0], 3400.0)
            # Lia invitée : ~2 m de Teome en repère cellule (y/z locaux)
            teome = by_id["player:Teome"]["pos"]
            lia = by_id["player:Lia"]["pos"]
            self.assertAlmostEqual(lia[0], teome[0], places=1)
            self.assertLess(abs(lia[1] - teome[1]), 2.0)
            self.assertLess(abs(lia[2] - teome[2]), 3.0)
            self.assertEqual(by_id["player:Lia"].get("local_pos"), [7.26, 0.35, 0.91])


if __name__ == "__main__":
    unittest.main()
