"""Workflow dev_game phase C — triage PM + action_proposal forge (dry-run par défaut)."""

from __future__ import annotations

import os
import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]


def forge_enabled() -> bool:
    return os.environ.get("LBG_TEAM_DEV_GAME_FORGE_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def auto_run_forge() -> bool:
    return os.environ.get("LBG_TEAM_DEV_GAME_AUTO_RUN_FORGE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _proposal_context(task: TeamTask) -> dict[str, object]:
    ctx: dict[str, object] = dict(task.context)
    ctx.setdefault("dev_game_focus", True)
    if task.context.get("_qa_followup"):
        ctx.setdefault("_qa_followup", True)
    return ctx


def execute_dev_game_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    """Brief PM + proposition forge OpenGame (optionnellement exécutée en dry-run)."""
    ctx = _proposal_context(task)
    brief_ctx = {
        **ctx,
        "project_pm": {
            "include_plan": True,
            "scope": "game_dev",
            "exclude_sandbox_mmmorpg": True,
        },
    }
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=brief_ctx,
    )

    proposal_payload: dict[str, object] | None = None
    forge_result: dict[str, object] | None = None

    if forge_enabled():
        prop = propose_action_from_text(task.objective, ctx)
        if prop.proposal is not None:
            proposal_payload = prop.proposal.model_dump()
            if auto_run_forge():
                patch = proposal_payload.get("context_patch")
                merged = {**ctx, **(patch if isinstance(patch, dict) else {})}
                routed = str(proposal_payload.get("routed_to") or "agent.opengame")
                forge_result = dispatch(
                    routed,
                    actor_id=task.actor_id,
                    text=task.objective,
                    context=merged,
                )

    ok = bool(brief.get("ok", True))
    if forge_result is not None and forge_result.get("ok") is False:
        ok = False

    out: dict[str, object] = {
        "kind": "dev_game_workflow",
        "ok": ok,
        "brief": brief,
    }
    if proposal_payload:
        out["action_proposal"] = proposal_payload
    if forge_result is not None:
        out["forge_dry_run"] = forge_result
    if forge_enabled() and proposal_payload is None:
        out["forge_note"] = (
            "Aucune proposition forge reconnue ; précisez forge/prototype/sandbox "
            "ou importez session_summary + mmo_bridge."
        )
    return out


def objective_suggests_forge(objective: str) -> bool:
    text = (objective or "").lower()
    return bool(
        re.search(
            r"\b(forge|forger|prototype|sandbox|opengame|correctif|bug|gameplay|investig|smoke)\b",
            text,
        )
    )
