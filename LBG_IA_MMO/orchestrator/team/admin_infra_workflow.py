"""Workflow admin_infra — capacité locale LLM, shortlist et bench."""

from __future__ import annotations

import os
from typing import Callable

from lbg_sa.atlas_memory import recall_atlas_hints, record_atlas_admin_infra_run
from team.admin_infra_element import maybe_notify_perimeter_ko
from team.admin_infra_platform import admin_infra_perimeter, audit_admin_infra_platform
from team.models import TeamTask
from team.ollama_audit import audit_ollama_lan
from team.reason_llm import reason_route_matrix

Dispatcher = Callable[..., dict[str, object]]


def _workstreams() -> list[dict[str, object]]:
    return [
        {
            "id": "audit_infra_locale_llm",
            "title": "Audit infra locale LLM",
            "owner_role": "admin_infra",
            "status": "planned",
        },
        {
            "id": "shortlist_bench_candidats",
            "title": "Shortlist + bench candidats",
            "owner_role": "qa",
            "status": "planned",
        },
        {
            "id": "routage_multi_modeles",
            "title": "Routage multi-modeles",
            "owner_role": "dev_game",
            "status": "planned",
        },
        {
            "id": "observabilite_admin_infra",
            "title": "Admin infra / observabilite",
            "owner_role": "ops",
            "status": "planned",
        },
    ]


def _candidate_models() -> list[dict[str, str]]:
    return [
        {
            "model": "qwen2.5:3b",
            "tier": "light_111_clean",
            "why": "router / json Clean sur NUC CT 111 (validé — pas gemma3:4b)",
        },
        {
            "model": "llama3.2:3b",
            "tier": "light_111_fast",
            "why": "triage Fast sur NUC CT 111",
        },
        {
            "model": "gemma4:e2b",
            "tier": "heavy_110_rapide",
            "why": "forge / failover light / jobs planner sur CT heavy 110",
        },
        {
            "model": "gemma4:26b",
            "tier": "heavy_110_raisonnement",
            "why": "code / PM / synthèse sur CT heavy 110",
        },
        {
            "model": "gemma4:12b",
            "tier": "milieu",
            "why": "compromis potentiel entre vitesse et profondeur",
        },
        {
            "model": "qwen-14b-instruct",
            "tier": "milieu",
            "why": "instruction following / code / multilingue",
        },
    ]


def execute_admin_infra_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    text = (task.objective or "").strip()
    ctx = dict(task.context)
    ctx.setdefault("subproject", "local_llm_lab")
    ctx.setdefault("admin_infra_focus", True)

    platform = audit_admin_infra_platform()
    ollama = platform.get("ollama_primary") if isinstance(platform.get("ollama_primary"), dict) else audit_ollama_lan()

    brief_ctx = {
        **ctx,
        "pm_focus": True,
        "project_pm": {
            "include_plan": True,
            "include_structure": True,
            "scope": "local_llm_lab",
            "subproject": "local_llm_lab",
        },
        "reunification_brief": True,
    }
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=text or "Plan operatoire local LLM lab",
        context=brief_ctx,
    )

    recommendations = list(ollama.get("recommendations") or [])
    recommendations.extend(platform.get("recommendations") or [])
    recommendations.extend(
        [
            "Fixer un budget local par role (rapide / raisonnement / JSON).",
            "Bench sur prompts LBG plutot que scores marketing.",
            "Rester 100% local pour raisonnement, code et routage agentique autant que possible.",
        ]
    )

    platform_ok = bool(platform.get("ok"))
    ollama_ok = bool(ollama.get("ok", False) or not ollama.get("error"))
    workflow_ok = bool(brief.get("ok", True)) and (platform_ok or ollama_ok)
    # Learn avant Element : une alerte Matrix ne doit pas bloquer l'archive LBG_SA.
    memory_record = record_atlas_admin_infra_run(
        task.id,
        platform=platform if isinstance(platform, dict) else {},
        ollama=ollama if isinstance(ollama, dict) else {},
        workflow_ok=workflow_ok,
    )
    memory_recall = recall_atlas_hints()
    try:
        perimeter_alert = maybe_notify_perimeter_ko(platform)
    except Exception as exc:  # noqa: BLE001 — ne pas faire échouer le run Atlas
        perimeter_alert = {"ok": False, "error": str(exc)}

    return {
        "kind": "admin_infra_workflow",
        "ok": workflow_ok,
        "brief": brief,
        "platform_audit": platform,
        "perimeter_element_alert": perimeter_alert,
        "ollama_audit": ollama,
        "workstreams": _workstreams(),
        "candidate_models": _candidate_models(),
        "bench_docs": [
            "docs/plan_team_local_llm.md",
            "docs/local_llm_bench_matrix.md",
            "docs/local_llm_bench_prompts.json",
            "infra/scripts/atlas_bench_watchdog.py",
        ],
        "watchdog": {
            "bench_min_oks": int(os.environ.get("LBG_ATLAS_BENCH_MIN_OKS", "3")),
            "bench_total": 6,
            "retry_ko_only": True,
            "timer": "lbg-atlas-bench-watchdog-job",
        },
        "subproject": "local_llm_lab",
        "persona": "Atlas",
        "role_scope": {
            "title": "Responsable plateforme LLM locale",
            "perimeter_hosts": admin_infra_perimeter(),
            "topology": {
                "llm_heavy": "192.168.0.110",
                "llm_light": "192.168.0.111",
                "front_legacy": "192.168.0.112",
            },
            "responsibilities": [
                "capacite",
                "deploiement",
                "bench",
                "stabilite",
                "watchdogs",
                "reprise_auto",
                "budgets_materiels",
                "routage_dual_110_111",
            ],
        },
        "constraints": {
            "prefer_local": True,
            "priority_axes": ["raisonnement", "code", "routage_agentique", "json_structure"],
            "dialogue_priority": "lower",
            "latency_110": os.environ.get(
                "LBG_LOCAL_LLM_LATENCY_POLICY",
                "hors dialogue: lenteur acceptable si gain qualitatif (heavy CT 110)",
            ),
            "latency_111": "Clean qwen2.5:3b + Fast llama3.2:3b sur NUC — latence faible ; gemma3:4b écarté",
        },
        "recommendations": recommendations,
        "route_matrix": reason_route_matrix(),
        "route_matrix_doc": "docs/local_llm_route_matrix.md",
        "lbg_sa_memory": {
            "record": memory_record,
            "recall": memory_recall,
        },
    }
