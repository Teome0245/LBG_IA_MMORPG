import pytest

from lbg_agents.dispatch import invoke_after_route


def test_quests_returns_structured_quest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    out = invoke_after_route(
        "agent.quests",
        actor_id="p:1",
        text="Je cherche une quête contre les loups",
        context={},
    )
    assert out["agent"] == "quests_stub"
    assert out["handler"] == "quests"
    quest = out["quest"]
    assert isinstance(quest, dict)
    assert "title" in quest
    assert "objectives" in quest and isinstance(quest["objectives"], list) and quest["objectives"]
    assert "rewards" in quest and isinstance(quest["rewards"], dict)
    st = out.get("quest_state")
    assert isinstance(st, dict)
    assert isinstance(st.get("quest_id"), str) and st["quest_id"]
    assert st.get("status") == "open"


def test_quests_progress_updates_when_quest_state_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    out1 = invoke_after_route(
        "agent.quests",
        actor_id="p:1",
        text="Une quête ?",
        context={},
    )
    qid = out1["quest_state"]["quest_id"]

    out2 = invoke_after_route(
        "agent.quests",
        actor_id="p:1",
        text="J'ai avancé.",
        context={"quest_state": {"quest_id": qid, "status": "open", "step": 0}},
    )
    st2 = out2.get("quest_state")
    assert isinstance(st2, dict)
    assert st2.get("quest_id") == qid
    assert st2.get("step") == 1


def test_quests_completed_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_QUESTS_URL", raising=False)
    out = invoke_after_route(
        "agent.quests",
        actor_id="p:1",
        text="Avancement",
        context={"quest_state": {"quest_id": "q-1", "status": "completed", "step": 2}},
    )
    st = out.get("quest_state")
    assert isinstance(st, dict)
    assert st.get("status") == "completed"
    assert st.get("step") == 2

