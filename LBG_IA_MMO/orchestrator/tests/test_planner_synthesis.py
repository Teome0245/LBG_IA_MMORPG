"""Planner : objectif « checkup et dis-moi quoi améliorer » → 2 étapes."""

from __future__ import annotations

from services.planner import plan_deterministic, plan_objective, split_objective
from services.action_proposal import propose_action_from_text


def test_split_checkup_et_synthesis() -> None:
    o = "peut tu me faire un auto checkup et me dire ce qui pourrait être amélioré"
    clauses = split_objective(o)
    assert len(clauses) == 2
    assert "checkup" in clauses[0].lower()
    assert "dire" in clauses[1].lower() or "amélior" in clauses[1].lower()


def test_plan_checkup_plus_synthesis_two_steps() -> None:
    o = "peut tu me faire un auto checkup et me dire ce qui pourrait être amélioré"
    plan = plan_deterministic(o, {"devops_dry_run": True})
    assert len(plan.steps) == 2
    assert plan.steps[0].capability == "devops_probe"
    assert plan.steps[0].action == {"kind": "selfcheck"}
    assert plan.steps[1].capability == "npc_dialogue"
    assert plan.steps[1].context_patch.get("_job_synthesis") is True


def test_plan_network_infra_survey_four_steps() -> None:
    o = "Analyse de l'environnement réseaux, et établissement de l'infra et des appareils présent."
    plan = plan_deterministic(o, {})
    assert len(plan.steps) == 4
    assert plan.steps[0].capability == "devops_probe"
    assert plan.steps[1].capability == "network_inventory"
    assert plan.steps[2].capability == "npc_dialogue"
    assert plan.steps[2].context_patch.get("_capabilities_inventory") is True
    assert plan.steps[3].capability == "npc_dialogue"
    assert plan.steps[3].context_patch.get("_job_synthesis") is True
    assert plan.reason and "réseau" in plan.reason


def test_plan_user_infra_objective_four_steps() -> None:
    """Formulation UI courante : « Analyse … réseau … infra … puis résume »."""
    o = (
        "Analyse l'environnement réseau et l'état de l'infra LBG "
        "(front 110, core 140, mmo prime 245, precu 246), puis résume l'état."
    )
    plan = plan_deterministic(o, {"devops_dry_run": True})
    assert len(plan.steps) == 4
    assert plan.steps[0].capability == "devops_probe"
    assert plan.steps[1].capability == "network_inventory"
    assert plan.steps[3].context_patch.get("_job_synthesis") is True


def test_plan_objective_network_survey_beats_llm_flag(monkeypatch) -> None:
    """Objectif réseau/infra : plan structuré 4 étapes même si planner LLM activé."""
    monkeypatch.setenv("LBG_JOBS_PLANNER_LLM", "1")
    o = "Analyse de l'environnement réseaux, et établissement de l'infra et des appareils présent."
    plan = plan_objective(o, {})
    assert len(plan.steps) == 4
    assert plan.steps[1].capability == "network_inventory"
    assert plan.source == "deterministic"


def test_synthesis_clause_proposal() -> None:
    r = propose_action_from_text("me dire ce qui pourrait être amélioré", {})
    assert r.proposal is not None
    assert r.proposal.capability == "npc_dialogue"
    assert r.proposal.context_patch.get("_job_synthesis") is True
