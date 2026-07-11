"""Tests sonde player_ia (Core3 Prime 246)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from team.player_ia_probe import probe_player_ia


class _Resp:
    def __init__(self, status_code: int, body: dict | None = None) -> None:
        self.status_code = status_code
        self.content = b"x"
        self._body = body or {}

    def json(self) -> dict:
        return self._body


def test_probe_player_ia_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CORE3_SIDECAR_URL", "http://246.test:8791")
    monkeypatch.setenv("LBG_CORE3_IA_BOTS", "lia,nix")

    def fake_get(url: str, params=None):  # noqa: ANN001
        if url.endswith("/healthz"):
            return _Resp(200, {"ok": True})
        if "player-snapshot" in url:
            player = (params or {}).get("player", "").lower()
            return _Resp(200, {"online": True, "player": player, "zone": "tatooine"})
        raise AssertionError(url)

    mock_client = MagicMock()
    mock_client.get.side_effect = fake_get
    mock_client.__enter__ = lambda s: mock_client
    mock_client.__exit__ = lambda *a: None

    with patch("team.player_ia_probe.httpx.Client", return_value=mock_client):
        out = probe_player_ia()
    assert out["ok"] is True
    assert out["online_count"] == 2


def test_probe_sidecar_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_CORE3_SIDECAR_URL", "http://246.test:8791")

    with patch("team.player_ia_probe.httpx.Client") as cls:
        inst = MagicMock()
        inst.__enter__ = lambda s: inst
        inst.__exit__ = lambda *a: None
        inst.get.side_effect = httpx.ConnectError("refused")
        cls.return_value = inst
        out = probe_player_ia()
    assert out["ok"] is False
