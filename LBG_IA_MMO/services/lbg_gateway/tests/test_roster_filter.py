"""Rosters exactly_one — un seul PNJ par roster."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from services.lbg_gateway.roster_filter import allow_roster_npc, roster_policies_from_catalog

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "content/core3/core3_npc_catalog.json"


class TestRosterFilter(unittest.TestCase):
    def test_barman_policy(self) -> None:
        doc = json.loads(CATALOG.read_text(encoding="utf-8"))
        policies = roster_policies_from_catalog(doc)
        self.assertEqual(policies.get("roster:mos_eisley_cantina_barman"), "exactly_one")

    def test_only_first_barman_kept(self) -> None:
        policies = {"roster:mos_eisley_cantina_barman": "exactly_one"}
        active: dict[str, str] = {}
        meta = {"roster_id": "roster:mos_eisley_cantina_barman"}
        self.assertTrue(allow_roster_npc("npc:core3_barman_jax", meta, policies, active))
        self.assertFalse(allow_roster_npc("npc:core3_barman_sira", meta, policies, active))


if __name__ == "__main__":
    unittest.main()
