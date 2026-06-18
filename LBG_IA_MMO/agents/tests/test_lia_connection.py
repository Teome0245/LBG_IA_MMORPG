"""Tests connexion Lia (orchestrateur → sidecar)."""

from __future__ import annotations

import json

import httpx

from lbg_agents.lia_connection import connect_lia, is_lia_online


def test_connect_already_online(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    assert is_lia_online() is True
    out = connect_lia()
    assert out["outcome"] == "already_online"


def test_connect_triggers_sidecar(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(409, json={"ok": False, "snapshot": {"online": False}})
        if request.url.path in ("/v1/lia/connect", "/v1/player/connect"):
            calls.append("connect")
            body = json.loads(request.content.decode())
            assert body.get("wait") is True
            return httpx.Response(200, json={"ok": True, "outcome": "connected"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    out = connect_lia(wait_s=30)
    assert calls == ["connect"]
    assert out["ok"] is True
    assert out["outcome"] == "connected"
