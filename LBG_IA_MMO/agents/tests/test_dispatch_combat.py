import pytest

from lbg_agents.dispatch import invoke_after_route


def test_combat_returns_structured_encounter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_COMBAT_URL", raising=False)
    out = invoke_after_route(
        "agent.combat",
        actor_id="p:1",
        text="Affrontement contre un loup",
        context={},
    )
    assert out["agent"] == "combat_stub"
    assert out["handler"] == "combat"
    enc = out["encounter"]
    assert isinstance(enc, dict)
    assert enc.get("opponent") == "Loup"
    assert enc.get("status") == "ongoing"
    assert isinstance(out.get("encounter_state"), dict)
    meta = out.get("meta")
    assert isinstance(meta, dict)
    assert meta.get("sterile") is True


def test_combat_continues_with_encounter_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_COMBAT_URL", raising=False)
    out1 = invoke_after_route(
        "agent.combat",
        actor_id="p:1",
        text="Attaquer le gobelin",
        context={},
    )
    es = out1["encounter_state"]
    assert isinstance(es, dict)
    out2 = invoke_after_route(
        "agent.combat",
        actor_id="p:1",
        text="Je frappe encore",
        context={"encounter_state": es},
    )
    enc2 = out2["encounter"]
    assert enc2["round"] == es["round"] + 1
    assert enc2["hp"]["opponent"] < es["hp"]["opponent"]
    assert enc2["encounter_id"] == es["encounter_id"]
