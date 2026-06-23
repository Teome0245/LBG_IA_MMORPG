"""Tests pont core3_bridge → sidecar."""

from __future__ import annotations

import json

import httpx
import pytest

from lbg_agents.core3_bridge import run_core3_bridge


def test_core3_missing_url():
    out = run_core3_bridge(
        actor_id="p:1",
        text="hi",
        context={"core3_action": {"kind": "npc_think", "npc_id": "npc:scribe"}},
    )
    assert out["ok"] is False
    assert out["outcome"] == "configuration_error"


def test_core3_npc_think_ok(monkeypatch):
    monkeypatch.setenv("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/npc-think"
        body = json.loads(request.content.decode())
        assert body["npc_id"] == "npc:scribe"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "action": "npc_say",
                "line": "npc_say|npc:core3_scribe|tatooine|0|0|0|Salut",
                "observation": "PNJ en ligne",
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real_client(transport=transport, *a, **k))

    out = run_core3_bridge(
        actor_id="p:1",
        text="Dis bonjour.",
        context={
            "core3_action": {"kind": "npc_think", "npc_id": "npc:scribe"},
        },
    )
    assert out["ok"] is True
    assert out["action"] == "npc_say"
