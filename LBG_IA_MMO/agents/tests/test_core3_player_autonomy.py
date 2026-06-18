"""Tests autonomie générique joueurs IA."""

from __future__ import annotations

import json

import httpx

from lbg_agents.core3_player_autonomy import build_player_prompt, player_autonomy_tick, route_context_for_player
from lbg_agents.core3_players import get_ai_player


def test_build_nix_prompt_mentions_scout():
    prompt = build_player_prompt(get_ai_player("nix"), tick_index=0)
    assert "Nix" in prompt
    assert "scout" in prompt
    assert "forage" in prompt


def test_route_context_uses_core3_player_think_contract():
    player = get_ai_player("nix")
    ctx = route_context_for_player(player, "observe")
    assert ctx["core3_player_id"] == "nix"
    assert ctx["core3_autonomy"] is True
    assert ctx["core3_action"]["kind"] == "player_think"
    assert ctx["core3_action"]["player"] == "Nix"
    assert ctx["core3_action"]["incarnation"] is False


def test_offline_player_skips(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"ok": False, "snapshot": {"online": False}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    out = player_autonomy_tick("nix")
    assert out["outcome"] == "skipped_offline"


def test_online_player_posts_think(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_MODE", "sidecar")
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "player": "Nix"}})
        if request.url.path == "/v1/think":
            body = json.loads(request.content.decode())
            calls.append(body)
            assert body["player"] == "Nix"
            assert body["incarnation"] is False
            return httpx.Response(200, json={"ok": True, "action": "perform", "line": "perform|Nix|tatooine|0|0|0|forage"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    out = player_autonomy_tick("nix")
    assert out["ok"] is True
    assert out["action"] == "perform"
    assert calls


def test_online_player_posts_orchestrator_route(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "player": "Nix"}})
        if request.url.path == "/v1/route":
            body = json.loads(request.content.decode())
            calls.append(body)
            assert body["actor_id"] == "orchestrator:nix"
            assert body["context"]["core3_action"]["kind"] == "player_think"
            assert body["context"]["core3_action"]["player"] == "Nix"
            return httpx.Response(
                200,
                json={
                    "intent": "core3_bot_action",
                    "confidence": 1.0,
                    "routed_to": "agent.core3",
                    "output": {
                        "ok": True,
                        "action": "interact",
                        "line": "interact|Nix|tatooine|0|0|0|assist:Lia",
                    },
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    out = player_autonomy_tick("nix")
    assert out["mode"] == "orchestrator"
    assert out["intent"] == "core3_bot_action"
    assert out["action"] == "interact"
    assert calls


def test_targeted_event_builds_reactive_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "player": "Nix"}})
        if request.url.path == "/v1/events":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "events": [
                        {
                            "event_id": "1-1",
                            "type": "core3.ai_say",
                            "actor": "Lia",
                            "target": "Nix",
                            "message": "Nix, peux-tu inspecter la zone ?",
                        }
                    ],
                    "last_event_id": "1-1",
                },
            )
        if request.url.path == "/v1/route":
            body = json.loads(request.content.decode())
            calls.append(body)
            assert "Lia" in body["text"]
            assert "inspecter la zone" in body["text"]
            return httpx.Response(
                200,
                json={
                    "intent": "core3_bot_action",
                    "confidence": 1.0,
                    "routed_to": "agent.core3",
                    "output": {"ok": True, "action": "say", "line": "say|Nix|tatooine|0|0|0|Bien reçu Lia."},
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    out = player_autonomy_tick("nix")
    assert out["ok"] is True
    assert out["social_event"]["event_id"] == "1-1"
    assert out["action"] == "say"
    assert calls


def test_human_spatial_chat_forage_is_deterministic(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")
    monkeypatch.setenv("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", str(tmp_path))
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/player-snapshot":
            return httpx.Response(200, json={"ok": True, "snapshot": {"online": True, "player": "Nix"}})
        if request.url.path == "/v1/events":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "events": [
                        {
                            "event_id": "2-1",
                            "type": "core3.player_spatial_chat",
                            "actor": "Teome",
                            "target": "Nix",
                            "message": "Nix tu peux executer l'action /forage ?",
                        }
                    ],
                    "last_event_id": "2-1",
                },
            )
        if request.url.path == "/v1/enqueue":
            body = json.loads(request.content.decode())
            calls.append(body)
            assert body["player"] == "Nix"
            assert body["action"] == "perform"
            assert body["message"] == "forage"
            return httpx.Response(200, json={"ok": True, "line": "perform|Nix|tatooine|0|0|0|forage"})
        if request.url.path == "/v1/route":
            raise AssertionError("direct human command should not call orchestrator")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client(*a, **k):
        k["transport"] = transport
        return real_client(*a, **k)

    monkeypatch.setattr(httpx, "Client", client)
    out = player_autonomy_tick("nix")
    assert out["ok"] is True
    assert out["mode"] == "deterministic_event"
    assert out["action"] == "perform"
    assert out["reason"] == "event_forage_request"
    assert out["social_event"]["event_id"] == "2-1"
    assert calls
