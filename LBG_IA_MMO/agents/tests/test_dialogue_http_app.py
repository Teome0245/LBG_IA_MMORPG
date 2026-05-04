import pytest
from fastapi.testclient import TestClient

from lbg_agents.dialogue_http_app import app


def test_world_content_inventory() -> None:
    client = TestClient(app)
    r = client.get("/world-content")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["races_count"] >= 10
    assert "race:human" in j["race_ids"]
    assert j["creatures_count"] == 50
    rd = j.get("race_display")
    assert isinstance(rd, dict) and rd.get("race:human") == "Humain"


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
    assert "desktop_plan_env_enabled" in j
    assert j["desktop_plan_env_enabled"] is False
    assert "dialogue_budget" in j
    assert j["dialogue_budget"]["enabled"] is False
    assert j.get("dialogue_target_default") == "local"


def test_healthz_desktop_plan_env_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DIALOGUE_DESKTOP_PLAN", "1")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("desktop_plan_env_enabled") is True


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
    assert j["meta"].get("dialogue_profile_resolved") == "professionnel"


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
            return {
                "choices": [
                    {
                        "message": {
                            "content": 'ACTION_JSON: {"kind":"aid","hunger_delta":-0.2,"thirst_delta":-0.1,"fatigue_delta":-0.2,"reputation_delta":5}\nBienvenue à la forge, voyageur.'
                        }
                    }
                ]
            }

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

    monkeypatch.setenv("LBG_DIALOGUE_WORLD_ACTIONS", "1")
    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "Salut", "context": {"npc_name": "Hagen", "world_npc_id": "npc:merchant"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["stub"] is False
    assert j["meta"]["llm"] is True
    assert j["reply"] == "Bienvenue à la forge, voyageur."
    assert j["meta"].get("dialogue_profile_resolved") == "professionnel"
    assert j["meta"]["cache_hit"] in (True, False)
    assert isinstance(j.get("commit"), dict)
    assert j["commit"]["flags"]["aid_hunger_delta"] == -0.2


def test_invoke_llm_action_json_quest_to_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    monkeypatch.setenv("LBG_DIALOGUE_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LBG_DIALOGUE_LLM_MODEL", "test-model")

    import lbg_agents.dialogue_llm as llm_mod

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": 'ACTION_JSON: {"kind":"quest","quest_id":"q:help_innkeeper","quest_step":1,"quest_accepted":true}\nParfait, je te confie cette mission.'
                        }
                    }
                ]
            }

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
    monkeypatch.setenv("LBG_DIALOGUE_WORLD_ACTIONS", "1")

    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "J'accepte", "context": {"npc_name": "Mara", "world_npc_id": "npc:innkeeper"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["reply"] == "Parfait, je te confie cette mission."
    assert isinstance(j.get("commit"), dict)
    assert j["commit"]["npc_id"] == "npc:innkeeper"
    flags = j["commit"]["flags"]
    assert flags["quest_id"] == "q:help_innkeeper"
    assert flags["quest_step"] == 1
    assert flags["quest_accepted"] is True


def test_invoke_llm_action_json_quest_reputation_to_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    monkeypatch.setenv("LBG_DIALOGUE_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LBG_DIALOGUE_LLM_MODEL", "test-model")

    import lbg_agents.dialogue_llm as llm_mod

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                'ACTION_JSON: {"kind":"quest","quest_id":"q:pay","quest_step":2,'
                                '"quest_accepted":true,"quest_completed":true,"reputation_delta":15}\nMerci.'
                            )
                        }
                    }
                ]
            }

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
    monkeypatch.setenv("LBG_DIALOGUE_WORLD_ACTIONS", "1")

    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "Voilà", "context": {"npc_name": "Mara", "world_npc_id": "npc:guard"}},
    )
    assert r.status_code == 200
    j = r.json()
    flags = j["commit"]["flags"]
    assert flags["reputation_delta"] == 15
    assert flags["quest_completed"] is True


def test_invoke_llm_action_json_quest_completed_to_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    monkeypatch.setenv("LBG_DIALOGUE_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LBG_DIALOGUE_LLM_MODEL", "test-model")

    import lbg_agents.dialogue_llm as llm_mod

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                'ACTION_JSON: {"kind":"quest","quest_id":"q:help_innkeeper","quest_step":3,'
                                '"quest_accepted":true,"quest_completed":true}\nBravo, c\'est fait.'
                            )
                        }
                    }
                ]
            }

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
    monkeypatch.setenv("LBG_DIALOGUE_WORLD_ACTIONS", "1")

    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "J'ai fini", "context": {"npc_name": "Mara", "world_npc_id": "npc:innkeeper"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert "Bravo" in j["reply"]
    flags = j["commit"]["flags"]
    assert flags["quest_completed"] is True
    assert flags["quest_step"] == 3


def test_healthz_shows_default_llm_when_not_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["llm_configured"] is True
    assert j["llm_model"] == "phi4-mini:latest"

