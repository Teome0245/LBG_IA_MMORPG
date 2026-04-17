import pytest
from fastapi.testclient import TestClient

from lbg_agents.dialogue_http_app import app


def test_healthz_includes_metadata() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["service"] == "dialogue_http"
    assert j["version"] == app.version
    assert "description" in j
    assert j["invoke"] == "POST /invoke"
    assert "llm_configured" in j
    assert j["llm_configured"] is False


def test_invoke_returns_rich_dialogue_shape_stub() -> None:
    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={
            "actor_id": "player:1",
            "text": "Bonjour forgeron",
            "context": {"npc_name": "Hagen le forgeron"},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["agent"] == "http_dialogue"
    assert j["speaker"] == "Hagen le forgeron"
    assert j["player_text"] == "Bonjour forgeron"
    assert isinstance(j["lines"], list) and len(j["lines"]) >= 2
    assert all(isinstance(x, str) for x in j["lines"])
    assert "Hagen le forgeron" in j["reply"]
    assert j["meta"]["stub"] is True
    assert j["meta"]["llm"] is False
    assert j["meta"]["agent_version"] == app.version


def test_invoke_default_speaker_when_no_npc_in_context() -> None:
    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "Salut", "context": {}},
    )
    assert r.status_code == 200
    assert r.json()["speaker"] == "PNJ"


def test_invoke_uses_llm_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    monkeypatch.setenv("LBG_DIALOGUE_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LBG_DIALOGUE_LLM_MODEL", "test-model")

    import lbg_agents.dialogue_llm as llm_mod

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "Bienvenue à la forge, voyageur."}}]}

    class _Client:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, *a: object, **k: object) -> _Resp:
            return _Resp()

    monkeypatch.setattr(llm_mod.httpx, "Client", lambda **kw: _Client())

    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "Salut", "context": {"npc_name": "Hagen"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["stub"] is False
    assert j["meta"]["llm"] is True
    assert j["reply"] == "Bienvenue à la forge, voyageur."
    assert j["meta"]["cache_hit"] in (True, False)


def test_healthz_shows_default_llm_when_not_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["llm_configured"] is True
    assert j["llm_model"] == "phi4-mini:latest"

