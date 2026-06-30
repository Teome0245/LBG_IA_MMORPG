"""Tests reconnexion bots IA."""

from __future__ import annotations

import httpx

from lbg_agents.core3_bot_connection import connect_player, ensure_ia_bots_online, is_player_online


def test_connect_player_uses_sidecar_endpoint(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player/connect":
            calls.append("connect")
            return httpx.Response(200, json={"ok": True, "outcome": "connected", "player": "Nix"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    monkeypatch.setattr("lbg_agents.core3_bot_connection.is_player_online", lambda _n: False)
    out = connect_player("nix", wait_s=30)
    assert calls == ["connect"]
    assert out["ok"] is True


def test_ensure_bots_respects_cooldown(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setattr("lbg_agents.core3_bot_connection.is_player_online", lambda _n: False)
    monkeypatch.setattr("lbg_agents.core3_bot_connection.prime_server_ready", lambda: True)
    monkeypatch.setattr(
        "lbg_agents.core3_bot_connection.fetch_snapshot",
        lambda _n: {"online": False, "reason": "snapshot_missing"},
    )
    monkeypatch.setattr(
        "lbg_agents.core3_bot_connection.connect_player",
        lambda *_a, **_k: {"ok": True, "outcome": "connected"},
    )
    first = ensure_ia_bots_online()
    second = ensure_ia_bots_online()
    assert first["ok"] is True
    assert second["bots"]["lia"]["outcome"] == "reconnect_cooldown"


def test_ensure_bots_zombie_bypasses_cooldown(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_IA_BOTS", "lia,nix")
    monkeypatch.setattr("lbg_agents.core3_bot_connection.is_player_online", lambda _n: False)
    monkeypatch.setattr("lbg_agents.core3_bot_connection.prime_server_ready", lambda: True)
    monkeypatch.setattr(
        "lbg_agents.core3_bot_connection.fetch_snapshot",
        lambda _n: {"online": False, "reason": "not_in_online_log"},
    )
    calls: list[bool] = []

    def fake_connect(*_a, force_restart=False, **_k):
        calls.append(bool(force_restart))
        return {"ok": True, "outcome": "connected"}

    monkeypatch.setattr("lbg_agents.core3_bot_connection.connect_player", fake_connect)
    ensure_ia_bots_online()
    ensure_ia_bots_online()
    assert len(calls) == 4
    assert all(calls)
