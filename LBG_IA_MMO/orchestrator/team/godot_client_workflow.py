"""Workflow dev_game — piste client Godot / lbg-ws/2 (audit + forge)."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.godot_supervisor import execute_godot_supervisor
from team.lbg_ws2_audit import audit_lbg_ws2_readiness
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]


def _is_godot_track(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("godot_track") or ctx.get("godot_client"):
        return True
    text = (task.objective or "").lower()
    return bool(
        re.search(
            r"\b(godot|lbg-ws|lbg_ws|prime-client|client.godot|gateway|zone.bridge|zone_bridge)\b",
            text,
        )
    )


def execute_godot_client_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    """Audit lbg-ws/2 + brief PM + proposition forge si objectif le suggère."""
    audit = audit_lbg_ws2_readiness()
    supervisor = execute_godot_supervisor(
        TeamTask(
            id=task.id,
            role="qa",
            objective=task.objective,
            status="running",
            priority=task.priority,
            approval_required=False,
            actor_id=task.actor_id,
            context={**task.context, "godot_mode": "audit"},
        )
    )

    brief_ctx = {
        **task.context,
        "project_pm": {
            "include_plan": True,
            "scope": "game_dev",
            "subproject": "client_godot",
            "exclude_sandbox_mmmorpg": True,
        },
        "subprojects_focus": ["client_godot", "core3_prime"],
    }
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=brief_ctx,
    )

    proposal_payload = None
    forge_result = None
    gaps = audit.get("gaps") if isinstance(audit.get("gaps"), list) else []
    forge_objective = task.objective
    if gaps:
        forge_objective = f"{task.objective} — implémenter: {gaps[0]}"

    prop = propose_action_from_text(forge_objective, task.context)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = "team_godot_client"
        proposal_payload.setdefault("summary", f"Prototype Godot/lbg-ws/2 — {gaps[0] if gaps else 'jalon suivant'}")

    ok = bool(brief.get("ok", True)) and bool(audit.get("ok", True))

    return {
        "kind": "godot_client_workflow",
        "ok": ok,
        "brief": brief,
        "lbg_ws2_audit": audit,
        "godot_supervisor": supervisor,
        "action_proposal": proposal_payload,
        "forge_dry_run": forge_result,
        "gaps": gaps,
        "next_actions": audit.get("next_actions"),
    }


def resolve_godot_client_workflow(task: TeamTask) -> bool:
    return _is_godot_track(task)
