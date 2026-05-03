import pytest

from lbg_agents.dispatch import invoke_after_route


def test_dialogue_stub_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DIALOGUE_URL", raising=False)
    out = invoke_after_route("agent.dialogue", actor_id="p:1", text="hello", context={})
    assert out["agent"] == "minimal_stub"
    assert out["handler"] == "dialogue"


class _FakeOk:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {
            "reply": "from-agent",
            "meta": {"dialogue_profile_resolved": "professionnel"},
        }


class _FakeClient:
    def __init__(self, *a: object, **k: object) -> None:
        pass

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def post(self, url: str, json: object | None = None) -> _FakeOk:
        assert url.endswith("/invoke")
        return _FakeOk()


def test_dialogue_http_when_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")
    import lbg_agents.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod.httpx, "Client", lambda **kw: _FakeClient())
    out = invoke_after_route("agent.dialogue", actor_id="p:1", text="hello", context={})
    assert out["agent"] == "http_dialogue"
    assert out["remote"]["reply"] == "from-agent"
    assert out.get("dialogue_profile_resolved") == "professionnel"


def test_dialogue_http_passes_stepped_lyra_to_invoke_and_returns_output_lyra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LBG_AGENT_DIALOGUE_URL", "http://127.0.0.1:8020")
    import lbg_agents.dispatch as dispatch_mod

    captured: dict[str, object] = {}

    class _CapturingClient:
        def __enter__(self) -> "_CapturingClient":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: object | None = None) -> _FakeOk:
            captured["posted"] = json
            return _FakeOk()

    monkeypatch.setattr(dispatch_mod.httpx, "Client", lambda **kw: _CapturingClient())
    ctx = {
        "lyra": {
            "gauges": {"hunger": 0.0, "thirst": 0.0, "fatigue": 0.0},
            "dt_s": 8000.0,
        }
    }
    out = invoke_after_route("agent.dialogue", actor_id="p:1", text="hello", context=ctx)
    assert out["agent"] == "http_dialogue"
    assert "lyra" in out
    posted = captured.get("posted")
    assert isinstance(posted, dict)
    inner = posted.get("context")
    assert isinstance(inner, dict)
    assert inner["lyra"]["gauges"]["hunger"] > 0.0
    assert out["lyra"]["gauges"]["hunger"] == inner["lyra"]["gauges"]["hunger"]
