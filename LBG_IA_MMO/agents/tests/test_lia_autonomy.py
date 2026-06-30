"""Tests boucle autonomie Lia."""

from __future__ import annotations

import json

import httpx
import pytest

from lbg_agents.lia_autonomy import lia_autonomy_tick


def test_snapshot_offline_skips(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_BOT_AUTO_CONNECT", "0")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"ok": False, "snapshot": {"online": False}})

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    out = lia_autonomy_tick()
    assert out["outcome"] == "skipped_offline"


def test_tick_sidecar_think(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_LIA_AUTONOMY_MODE", "sidecar")
    monkeypatch.setenv("LBG_CORE3_LIA_AUTONOMY_PROMPT", "Dis bonjour.")
    monkeypatch.setattr("lbg_agents.lia_orchestrator.deterministic_proactive_action", lambda *a, **k: None)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "zone": "tatooine"}})
        if request.url.path == "/v1/think":
            body = json.loads(request.content.decode())
            assert body["player"] == "Lia"
            assert body.get("incarnation") is True
            return httpx.Response(
                200,
                json={"ok": True, "action": "say", "line": "say|Lia|tatooine|0|0|0|Salut"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr(
        "lbg_agents.lia_orchestrator.fetch_brain_status",
        lambda: None,
    )
    out = lia_autonomy_tick()
    assert out["ok"] is True
    assert out["action"] == "say"
