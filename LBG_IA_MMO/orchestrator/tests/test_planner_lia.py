"""Planner : objectifs pilotage Lia en MMO."""

from __future__ import annotations

from services.action_proposal import propose_action_from_text
from services.planner import plan_deterministic, plan_objective


def test_action_proposal_lia_mmo() -> None:
    r = propose_action_from_text("Fais jouer Lia un tour sur Tatooine", {})
    assert r.proposal is not None
    assert r.proposal.capability == "core3_bot_action"
    assert r.proposal.action.get("kind") == "player_think"
    assert r.proposal.action.get("player") == "Lia"
    assert r.proposal.context_patch.get("lia_incarnation") is True


def test_plan_lia_single_step() -> None:
    o = "Fais jouer Lia un tour sur Tatooine"
    plan = plan_deterministic(o, {})
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "core3_bot_action"
    assert plan.steps[0].context_patch.get("core3_player_id") == "lia"
    assert plan.reason and "lia" in plan.reason.lower()


def test_plan_lia_with_synthesis() -> None:
    o = "Fais jouer Lia un tour en MMO et dis-moi ce qu'elle observe"
    plan = plan_deterministic(o, {})
    assert len(plan.steps) == 2
    assert plan.steps[0].capability == "core3_bot_action"
    assert plan.steps[1].capability == "npc_dialogue"
    assert plan.steps[1].context_patch.get("_job_synthesis") is True


def test_plan_objective_lia_beats_llm_flag(monkeypatch) -> None:
    monkeypatch.setenv("LBG_JOBS_PLANNER_LLM", "1")
    o = "Pilote Lia en jeu — observe la zone"
    plan = plan_objective(o, {})
    assert plan.steps[0].capability == "core3_bot_action"
    assert plan.source == "deterministic"
