"""Garde-fous taille / encodage des frames WebSocket entrantes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mmmorpg_server.main import _format_ia_placeholder, _inbound_to_utf8


class TestWsInbound(unittest.TestCase):
    def test_accepts_short_str(self):
        text, err = _inbound_to_utf8('{"type":"hello"}')
        self.assertIsNone(err)
        self.assertEqual(text, '{"type":"hello"}')

    def test_rejects_oversize_bytes(self):
        with patch("mmmorpg_server.main.config.MAX_WS_INBOUND_BYTES", 8):
            text, err = _inbound_to_utf8(b"123456789")
            self.assertIsNone(text)
            self.assertIn("volumineux", err or "")

    def test_rejects_bad_utf8(self):
        with patch("mmmorpg_server.main.config.MAX_WS_INBOUND_BYTES", 100):
            text, err = _inbound_to_utf8(b"\xff\xfe")
            self.assertIsNone(text)
            self.assertIn("UTF-8", err or "")

    def test_placeholder_uses_npc_name(self):
        out = _format_ia_placeholder(
            "…un instant. (Le PNJ vous regarde, comme s’il réfléchissait.)",
            "Garde",
        )
        self.assertIn("Garde vous regarde", out)
        self.assertNotIn("Le PNJ", out)


if __name__ == "__main__":
    unittest.main()
