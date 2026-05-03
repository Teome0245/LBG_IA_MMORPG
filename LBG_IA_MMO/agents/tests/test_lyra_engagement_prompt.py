"""Rang 2 ADR 0004 : lyra_engagement + session_summary dans le prompt dialogue."""

from __future__ import annotations

from lbg_agents import dialogue_llm


def test_resolve_mmo_persona_from_world_npc_id() -> None:
    assert (
        dialogue_llm.resolve_lyra_engagement({"world_npc_id": "npc:x", "lyra_engagement": "local_assistant"})
        == "mmo_persona"
    )


def test_resolve_local_when_desktop_plan() -> None:
    ctx = {"_desktop_plan": True, "world_npc_id": "npc:x"}
    # env peut activer le plan ; forcer via monkeypatch serait idéal, mais _desktop_plan suffit si env off
    import os

    old = os.environ.get("LBG_DIALOGUE_DESKTOP_PLAN")
    try:
        os.environ["LBG_DIALOGUE_DESKTOP_PLAN"] = "1"
        assert dialogue_llm.resolve_lyra_engagement(ctx) == "local_assistant"
    finally:
        if old is None:
            os.environ.pop("LBG_DIALOGUE_DESKTOP_PLAN", None)
        else:
            os.environ["LBG_DIALOGUE_DESKTOP_PLAN"] = old


def test_build_prompt_includes_mmo_engagement_paragraph() -> None:
    p = dialogue_llm.build_system_prompt(
        "Mara",
        {"world_npc_id": "npc:innkeeper", "session_summary": {"tracked_quest": "q-help"}},
    )
    assert "persona MMO" in p
    assert "Quête suivie" in p
    assert "q-help" in p


def test_build_prompt_includes_quest_snapshot() -> None:
    p = dialogue_llm.build_system_prompt(
        "Mara",
        {
            "world_npc_id": "npc:innkeeper",
            "session_summary": {"quest_snapshot": "id=q:x step=1"},
        },
    )
    assert "Instantané quête" in p
    assert "step=1" in p


def test_desktop_plan_includes_session_summary() -> None:
    import os

    old = os.environ.get("LBG_DIALOGUE_DESKTOP_PLAN")
    try:
        os.environ["LBG_DIALOGUE_DESKTOP_PLAN"] = "1"
        p = dialogue_llm.build_system_prompt(
            "Assistant",
            {
                "_desktop_plan": True,
                "session_summary": {"player_note": "hier au village"},
            },
        )
        assert "Résumé MMO" in p or "session_summary" in p.lower()
        assert "village" in p
    finally:
        if old is None:
            os.environ.pop("LBG_DIALOGUE_DESKTOP_PLAN", None)
        else:
            os.environ["LBG_DIALOGUE_DESKTOP_PLAN"] = old
