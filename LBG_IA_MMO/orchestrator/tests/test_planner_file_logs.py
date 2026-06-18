"""Planner jobs : chemins fichier et demandes logs."""

from __future__ import annotations

from services.planner import plan_deterministic


def test_plan_file_path_uses_pm() -> None:
    plan = plan_deterministic("donne moi le chemin du fichier a modifier", {})
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "project_pm"


def test_plan_capabilities_inventory_uses_dialogue() -> None:
    plan = plan_deterministic("établie la liste des agents disponible et leurs capacité", {})
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "npc_dialogue"
    assert plan.steps[0].context_patch.get("_capabilities_inventory") is True


def test_plan_logs_uses_dialogue() -> None:
    plan = plan_deterministic(
        "ajoute un système de logs pour facilité le débogage, avec une rétention maximal de 30 jours",
        {},
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "npc_dialogue"
