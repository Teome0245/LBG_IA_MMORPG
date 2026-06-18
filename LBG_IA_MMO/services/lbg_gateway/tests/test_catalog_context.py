"""Tests contexte catalogue Core3 → dialogue Prime."""

from __future__ import annotations

import unittest
from pathlib import Path

from services.lbg_gateway.catalog_context import build_dialogue_context

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "content/core3/core3_npc_catalog.json"


class TestCatalogContext(unittest.TestCase):
    def test_barman_jax_identity(self) -> None:
        ctx = build_dialogue_context(
            "npc:core3_barman_jax",
            catalog_path=CATALOG,
            npc_name="Jax Moro",
        )
        ss = ctx.get("session_summary")
        self.assertIsInstance(ss, dict)
        last = str(ss.get("last_npc", ""))
        mem = str(ss.get("memory_hint", ""))
        self.assertIn("Jax Moro", last)
        self.assertIn("barman", last.lower())
        self.assertIn("forgeron", mem.lower())
        self.assertIn("Interdit", mem)
        self.assertEqual(ctx.get("world_npc_id"), "npc:core3_barman_jax")


if __name__ == "__main__":
    unittest.main()
