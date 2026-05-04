from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import httpx

import api.v1.routes.pilot as pilot_mod
from models.intents import IntentResponse


class _FakeResp:
    status_code = 200

    def json(self) -> dict:
        return {"status": "ok", "accepted": True, "reason": "accepted"}

    @property
    def text(self) -> str:
        return "ok"


class _FakeAsyncClient:
    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str, json: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
        assert "/internal/v1/npc/npc:merchant/dialogue-commit" in url
        assert isinstance(json, dict)
        assert json.get("trace_id")
        return _FakeResp()


def _fake_async_client(*args: object, **kwargs: object) -> _FakeAsyncClient:
    return _FakeAsyncClient()


class _CaptureOrch:
    async def route_intent(self, payload: object) -> IntentResponse:
        return IntentResponse(
            intent="npc_dialogue",
            confidence=0.9,
            routed_to="agent.dialogue",
            output={
                "reply": "ok",
                "commit": {"npc_id": "npc:merchant", "flags": {"quest_accepted": True}},
            },
        )


def test_pilot_route_attempts_commit_when_output_commit_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)
    # Désactiver la sync Lyra monde pour que ce test ne fasse pas d'autres GET HTTP.
    monkeypatch.delenv("LBG_MMO_SERVER_URL", raising=False)
    monkeypatch.delenv("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", raising=False)

    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _CaptureOrch())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={
            "actor_id": "p:1",
            "text": "Bonjour",
            "context": {"world_npc_id": "npc:merchant"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data.get("commit_result", {}).get("ok") is True
    assert data["commit_result"]["accepted"] is True


def test_pilot_route_filters_unsupported_flags_before_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Le backend fait un pré-filtrage best-effort : il ne doit pas pousser des clés inconnues.
    L'autorité finale reste côté serveur jeu.
    """
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setenv("LBG_MMMORPG_COMMIT_ALLOWED_FLAGS", "quest_id")
    monkeypatch.delenv("LBG_MMO_SERVER_URL", raising=False)
    monkeypatch.delenv("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", raising=False)

    captured: dict[str, object] = {}

    class _Client(_FakeAsyncClient):
        async def post(self, url: str, json: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
            assert isinstance(json, dict)
            captured["json"] = json
            return _FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _Client())

    class _OrchBad:
        async def route_intent(self, payload: object) -> IntentResponse:
            return IntentResponse(
                intent="npc_dialogue",
                confidence=0.9,
                routed_to="agent.dialogue",
                output={
                    "reply": "ok",
                    "commit": {"npc_id": "npc:merchant", "flags": {"quest_id": "q:1", "__bad": "x"}},
                },
            )

    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _OrchBad())

    from backend.main import app

    client = TestClient(app)
    r = client.post("/v1/pilot/route", json={"actor_id": "p:1", "text": "x", "context": {"world_npc_id": "npc:merchant"}})
    assert r.status_code == 200
    sent = captured.get("json")
    assert isinstance(sent, dict)
    flags = sent.get("flags")
    assert isinstance(flags, dict)
    assert "__bad" not in flags
    assert flags.get("quest_id") == "q:1"


def test_pilot_route_commit_rejected_when_flag_value_type_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.setenv("LBG_MMMORPG_COMMIT_ALLOWED_FLAGS", "quest_id")
    monkeypatch.delenv("LBG_MMO_SERVER_URL", raising=False)
    monkeypatch.delenv("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", raising=False)

    # Ne doit pas appeler httpx si validation backend échoue.
    called = {"post": 0}

    class _Client(_FakeAsyncClient):
        async def post(self, url: str, json: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
            called["post"] += 1
            return _FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _Client())

    class _OrchBadType:
        async def route_intent(self, payload: object) -> IntentResponse:
            return IntentResponse(
                intent="npc_dialogue",
                confidence=0.9,
                routed_to="agent.dialogue",
                output={
                    "reply": "ok",
                    "commit": {"npc_id": "npc:merchant", "flags": {"quest_id": {"nope": 1}}},
                },
            )

    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _OrchBadType())

    from backend.main import app

    client = TestClient(app)
    r = client.post("/v1/pilot/route", json={"actor_id": "p:1", "text": "x", "context": {"world_npc_id": "npc:merchant"}})
    assert r.status_code == 200
    data = r.json()
    cr = data.get("commit_result")
    assert isinstance(cr, dict)
    assert cr.get("ok") is False
    assert cr.get("error") == "invalid_commit_flags"
    assert called["post"] == 0


def test_pilot_route_commit_passes_player_id_for_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le backend envoie ``player_id`` au commit interne pour les flags ``player_item_*``."""
    monkeypatch.setenv("LBG_MMMORPG_INTERNAL_HTTP_URL", "http://127.0.0.1:8773")
    monkeypatch.delenv("LBG_MMO_SERVER_URL", raising=False)
    monkeypatch.delenv("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", raising=False)

    captured: dict[str, object] = {}

    class _Client(_FakeAsyncClient):
        async def post(self, url: str, json: object | None = None, headers: object | None = None) -> _FakeResp:  # type: ignore[override]
            captured["json"] = json
            return _FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _Client())

    class _OrchInv:
        async def route_intent(self, payload: object) -> IntentResponse:
            return IntentResponse(
                intent="npc_dialogue",
                confidence=0.9,
                routed_to="agent.dialogue",
                output={
                    "commit": {
                        "npc_id": "npc:merchant",
                        "flags": {"player_item_id": "item:x", "player_item_qty_delta": 1},
                    },
                },
            )

    monkeypatch.setattr(pilot_mod.OrchestratorClient, "from_env", lambda: _OrchInv())

    from backend.main import app

    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    client = TestClient(app)
    r = client.post(
        "/v1/pilot/route",
        json={
            "actor_id": f"player:{pid}",
            "text": "Donne-moi un objet",
            "context": {"world_npc_id": "npc:merchant"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("commit_result", {}).get("ok") is True
    sent = captured.get("json")
    assert isinstance(sent, dict)
    assert sent.get("player_id") == pid
