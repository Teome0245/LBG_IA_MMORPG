"""Workflow dev_game — build Core3 ZB-0 (plan L1 / compile L2)."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.core3_build_probe import (
    build_requires_approval,
    check_build_log_tail,
    probe_core3_build_plan,
    run_core3_build,
)
from team.human_summary import format_validation_summary
from team.lbg_ws2_audit import audit_zb0_readiness
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]


def _is_core3_build(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("core3_build") or ctx.get("subproject") == "core3_build":
        return True
    text = (task.objective or "").lower()
    return bool(
        re.search(
            r"\b(build|compiler|compile|cmake|antigravity|core3.?build|zb-?0.?build)\b.*\b(core3|zb|zone.?bridge)\b"
            r"|\bcompiler core3\b",
            text,
        )
    )


def _execute_build(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("core3_build_execute") is True:
        return True
    text = (task.objective or "").lower()
    return "compiler" in text or "build réel" in text or "execute build" in text


def execute_core3_build_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    ctx = dict(task.context)
    ctx.setdefault("subproject", "core3_build")
    ctx.setdefault("dev_game_focus", True)

    zb0 = audit_zb0_readiness()
    execute = _execute_build(task)
    plan_probe = probe_core3_build_plan(execute=execute)

    build_result = None
    log_tail = None
    if execute:
        if build_requires_approval() and not task.stored_approval_token:
            return {
                "kind": "core3_build_workflow",
                "ok": False,
                "error": "Build Core3 requiert approbation L2 (token)",
                "needs_approval": True,
                "plan": plan_probe.get("plan"),
                "zb0": zb0,
            }
        build_result = run_core3_build(sync=True)
        log_tail = check_build_log_tail()

    probes = [zb0, plan_probe]
    if ctx.get("parallel_prime") or ctx.get("poll_build_log"):
        polled = check_build_log_tail()
        if polled:
            log_tail = polled
            probes.append({"track": "core3_build_log", **polled})
    if build_result:
        probes.append({"track": "core3_build_run", **build_result})
    if log_tail and not any(p.get("track") == "core3_build_log" for p in probes):
        probes.append({"track": "core3_build_log", **log_tail})

    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context={
            **ctx,
            "project_pm": {"scope": "game_dev", "subproject": "core3_build"},
            "subprojects_focus": ["core3_prime", "client_godot"],
        },
    )

    forge_objective = (
        f"prototype ZB-0 hook ZoneServer — {task.objective}"
        if not execute
        else f"corriger build Core3 — {(build_result or {}).get('stderr_tail', '')[:200]}"
    )
    proposal_payload = None
    prop = propose_action_from_text(forge_objective, ctx)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = "team_core3_build"
        proposal_payload.setdefault("summary", "Prototype / patch ZB-0 — revue avant merge Core3")

    ok = bool(zb0.get("ok")) and bool(plan_probe.get("ok"))
    if execute and build_result:
        ok = ok and bool(build_result.get("ok"))

    checklist = [
        "Vérifier human_summary ci-dessus",
        "Si build L2 lancé : tail log VM 246 (/tmp/core3-antigravity-build.log)",
        "Après [100%] : install_core3_clean + restart Prime",
        "Valider Godot preset « Valider client » ou sidecar smoke",
    ]

    human_summary = format_validation_summary(
        title="Vulcan — build Core3 ZB-0",
        probes=probes,
        build_plan=plan_probe.get("plan") if isinstance(plan_probe.get("plan"), dict) else None,
        forge_note=(proposal_payload or {}).get("summary") if proposal_payload else None,
        checklist=checklist if not execute else checklist[1:],
    )

    return {
        "kind": "core3_build_workflow",
        "ok": ok,
        "persona": "Vulcan",
        "subproject": "core3_build",
        "zb0": zb0,
        "plan": plan_probe.get("plan"),
        "build_result": build_result,
        "log_tail": log_tail,
        "brief": brief,
        "action_proposal": proposal_payload,
        "human_summary": human_summary,
        "execute_mode": execute,
    }


def resolve_core3_build_workflow(task: TeamTask) -> bool:
    return _is_core3_build(task)
