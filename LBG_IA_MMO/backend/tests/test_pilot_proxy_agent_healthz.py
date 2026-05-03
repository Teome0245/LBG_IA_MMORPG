import pytest
from fastapi.testclient import TestClient

import api.v1.routes.pilot as pilot_mod


class _FakeOk:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {"status": "ok", "service": "dialogue_http"}


class _FakeClient:
    def __init__(self, *a: object, **k: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def get(self, url: str) -> _FakeOk:
        assert url.endswith("/healthz")
        return _FakeOk()


def test_pilot_proxy_dialogue_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DIALOGUE_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("skipped") is True


def test_pilot_proxy_dialogue_world_content_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DIALOGUE_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/world-content")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_dialogue_world_content_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")

    class _OkWorld:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "ok": True,
                "races_count": 14,
                "race_ids": ["race:human"],
                "creatures_count": 50,
            }

    class _ClientWorld:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientWorld":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _OkWorld:
            assert url.endswith("/world-content")
            return _OkWorld()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientWorld())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/world-content")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("creatures_count") == 50
    assert "race:human" in (j.get("race_ids") or [])


def test_pilot_proxy_dialogue_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")
    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-dialogue/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "dialogue_http"


def test_pilot_proxy_quests_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-quests/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_combat_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_COMBAT_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-combat/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_combat_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_COMBAT_URL", "http://127.0.0.1:8040")

    class _OkCombat:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"status": "ok", "service": "combat_http", "version": "0.2.0"}

    class _ClientCombat:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientCombat":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _OkCombat:
            assert url.endswith("/healthz")
            return _OkCombat()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientCombat())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-combat/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "combat_http"


def test_pilot_proxy_pm_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_PM_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-pm/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_pm_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_PM_URL", "http://127.0.0.1:8055")

    class _OkPm:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"status": "ok", "service": "pm_http"}

    class _ClientPm:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientPm":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _OkPm:
            assert url.endswith("/healthz")
            return _OkPm()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientPm())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-pm/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "pm_http"


def test_pilot_proxy_desktop_skipped_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DESKTOP_URL", raising=False)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-desktop/healthz")
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_pilot_proxy_desktop_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DESKTOP_URL", "http://127.0.0.1:8060")

    class _OkDesktop:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"status": "ok", "service": "desktop_http"}

    class _ClientDesktop:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientDesktop":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, url: str) -> _OkDesktop:
            assert url.endswith("/healthz")
            return _OkDesktop()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientDesktop())

    from backend.main import app

    client = TestClient(app)
    r = client.get("/v1/pilot/agent-desktop/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("service") == "desktop_http"


def test_pilot_proxy_agent_dialogue_invoke_forwards_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")
    captured: dict[str, object] = {}

    class _OkInvoke:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "agent": "http_dialogue",
                "reply": "Salut.",
                "lines": ["Salut."],
                "speaker": "PNJ",
                "player_text": "Hi",
                "actor_id": "p:1",
                "meta": {
                    "stub": False,
                    "llm": True,
                    "dialogue_profile_resolved": "professionnel",
                },
            }

    class _ClientInvoke:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> "_ClientInvoke":
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object] | None = None) -> _OkInvoke:
            captured["url"] = url
            captured["json"] = json
            return _OkInvoke()

    monkeypatch.setattr(pilot_mod.httpx, "AsyncClient", lambda **kw: _ClientInvoke())

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/pilot/agent-dialogue/invoke",
        json={"actor_id": "p:1", "text": "Hi", "context": {"world_npc_id": "npc:merchant"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("reply") == "Salut."
    meta = j.get("meta")
    assert isinstance(meta, dict)
    assert meta.get("dialogue_profile_resolved") == "professionnel"
    assert captured.get("url") == "http://127.0.0.1:8020/invoke"
    body = captured.get("json")
    assert isinstance(body, dict)
    assert body.get("actor_id") == "p:1"
    assert body.get("text") == "Hi"
    assert isinstance(body.get("context"), dict)
