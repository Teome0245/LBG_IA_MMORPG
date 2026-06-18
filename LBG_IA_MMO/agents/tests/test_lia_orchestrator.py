"""Tests incarnation Lia (orchestrateur → sidecar)."""

from __future__ import annotations

import json

import httpx
import pytest

from lbg_agents.lia_orchestrator import (
    autonomy_tick,
    build_hear_prompt,
    build_social_event_prompt,
    hear_player_message,
    lia_system_prompt,
    route_context_for_incarnation,
)


def test_lia_system_prompt_contains_identity():
    prompt = lia_system_prompt()
    assert "Lia" in prompt
    assert "say" in prompt


def test_build_hear_prompt_includes_message():
    p = build_hear_prompt(from_player="Teome", text="Salut Lia", brain=None)
    assert "Teome" in p
    assert "Salut Lia" in p


def test_build_social_event_prompt_prioritizes_actor():
    p = build_social_event_prompt(
        {"type": "core3.ai_say", "actor": "Nix", "target": "Lia", "message": "Lia, que dois-je faire ?"},
        brain=None,
    )
    assert "Nix" in p
    assert "que dois-je faire" in p


def test_route_context_marks_incarnation():
    ctx = route_context_for_incarnation(prompt="test", from_player="Teome")
    assert ctx["lia_incarnation"] is True
    action = ctx["core3_action"]
    assert action["kind"] == "player_think"
    assert action["incarnation"] is True


def test_hear_player_sidecar(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_LIA_HEAR_VIA", "sidecar")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/think":
            body = json.loads(request.content.decode())
            assert body.get("incarnation") is True
            assert "Teome" in body["prompt"]
            return httpx.Response(200, json={"ok": True, "action": "say"})
        if request.url.path.endswith("/brain/status"):
            return httpx.Response(404)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr("lbg_agents.lia_orchestrator.fetch_brain_status", lambda: None)
    out = hear_player_message(from_player="Teome", text="Où es-tu ?")
    assert out.get("incarnation") is True
    assert out.get("ok") is True


def test_hear_player_dance_is_deterministic(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/enqueue":
            body = json.loads(request.content.decode())
            assert body["action"] == "perform"
            assert body["message"] == "dance"
            return httpx.Response(200, json={"ok": True, "line": "perform|Lia|tatooine|0|0|0|dance"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr("lbg_agents.lia_connection.lia_auto_connect_enabled", lambda: False)
    out = hear_player_message(from_player="Teome", text="si tu peux danser pour moi ?")
    assert out["ok"] is True
    assert out["mode"] == "deterministic_hear"
    assert out["reason"] == "hear_dance_request"


def test_hear_dance_with_style_hint(monkeypatch):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/enqueue":
            body = json.loads(request.content.decode())
            captured["message"] = body.get("message", "")
            return httpx.Response(200, json={"ok": True, "line": f"perform|Lia|tatooine|0|0|0|{captured['message']}"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr("lbg_agents.lia_connection.lia_auto_connect_enabled", lambda: False)
    out = hear_player_message(from_player="Teome", text="Lia, danse exotic")
    assert out["ok"] is True
    assert captured.get("message") == "dance:exotic"


def test_lia_autonomy_uses_targeted_social_event(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_LIA_AUTONOMY_MODE", "sidecar")
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "player": "Lia"}})
        if request.url.path == "/v1/events":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "events": [
                        {
                            "event_id": "2-1",
                            "type": "core3.ai_say",
                            "actor": "Nix",
                            "target": "Lia",
                            "message": "Lia, quelle action dois-je coordonner ?",
                        }
                    ],
                    "last_event_id": "2-1",
                },
            )
        if request.url.path == "/v1/think":
            body = json.loads(request.content.decode())
            calls.append(body)
            assert body["incarnation"] is True
            assert "Nix" in body["prompt"]
            assert "quelle action" in body["prompt"]
            return httpx.Response(200, json={"ok": True, "action": "say", "line": "say|Lia|tatooine|0|0|0|Nix, explore."})
        if request.url.path.endswith("/brain/status"):
            return httpx.Response(404)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    _real_client = httpx.Client

    def _client(*a, **k):
        k["transport"] = transport
        return _real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr("lbg_agents.lia_orchestrator.fetch_brain_status", lambda: None)
    monkeypatch.setattr("lbg_agents.lia_connection.lia_auto_connect_enabled", lambda: False)
    out = autonomy_tick()
    assert out["ok"] is True
    assert out["social_event"]["event_id"] == "2-1"
    assert calls
