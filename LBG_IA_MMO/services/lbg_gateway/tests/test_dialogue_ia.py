"""Tests unitaires pont IA gateway (sans réseau)."""

from __future__ import annotations

import os
import unittest

from services.lbg_gateway.dialogue_ia import _extract_reply, placeholder_reply


class TestDialogueIa(unittest.TestCase):
    def test_extract_reply_from_remote(self) -> None:
        payload = {
            "trace_id": "abc123",
            "result": {"output": {"remote": {"reply": "Bienvenue sur Tatooine."}}},
        }
        text, tid = _extract_reply(payload)
        self.assertEqual(text, "Bienvenue sur Tatooine.")
        self.assertEqual(tid, "abc123")

    def test_placeholder(self) -> None:
        self.assertIn("Jax", placeholder_reply("Jax Moro"))

    def test_ia_not_configured_without_url(self) -> None:
        os.environ.pop("LBG_GATEWAY_IA_BACKEND_URL", None)
        os.environ.pop("MMMORPG_IA_BACKEND_URL", None)
        import importlib
        import services.lbg_gateway.dialogue_ia as mod

        importlib.reload(mod)
        self.assertFalse(mod.ia_configured())


if __name__ == "__main__":
    unittest.main()
