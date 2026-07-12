"""Workflow dev_game — piste Infographiste IA (assets GLB Godot)."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.infographiste_probe import probe_infographiste_assets
from team.comfyui_media import comfyui_enabled, generate_asset_for_gap, probe_comfyui
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]


def _is_infographiste_track(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("infographiste_ia") or ctx.get("subproject") == "infographiste_ia":
        return True
    text = (task.objective or "").lower()
    return bool(
        re.search(
            r"\b(infographiste|infograph|pipeline.?assets|\.glb|blender|textures? 3d|assets? 3d|swg.?godot)\b",
            text,
        )
    )


def execute_infographiste_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    ctx = dict(task.context)
    ctx.setdefault("subproject", "infographiste_ia")
    ctx.setdefault("infographiste_ia", True)
    ctx.setdefault("dev_game_focus", True)

    probe = probe_infographiste_assets(task)

    brief_ctx = {
        **ctx,
        "project_pm": {
            "include_plan": True,
            "scope": "game_dev",
            "subproject": "infographiste_ia",
            "exclude_sandbox_mmmorpg": True,
        },
        "subprojects_focus": ["infographiste_ia", "client_godot"],
        "reunification_brief": True,
    }
    from team.subprojects import list_subprojects

    brief_ctx["subprojects"] = [sp for sp in list_subprojects() if sp.get("id") == "infographiste_ia"] or list_subprojects()

    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=brief_ctx,
    )

    forge_objective = task.objective
    missing = probe.get("glb_missing") if isinstance(probe.get("glb_missing"), list) else []
    if missing:
        forge_objective = (
            f"prototype pipeline assets Infographiste — produire ou planifier GLB manquant : {missing[0]}"
        )
    elif not re.search(r"\b(forge|prototype|opengame|correctif|bug|gameplay)\b", forge_objective, re.I):
        forge_objective = f"prototype pipeline assets Infographiste GLB Godot — {forge_objective}"

    proposal_payload = None
    prop = propose_action_from_text(forge_objective, ctx)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = "team_infographiste_ia"
        proposal_payload.setdefault(
            "summary",
            "Prototype pipeline assets Infographiste IA (GLB Godot) — revue humaine avant import",
        )
        patch = proposal_payload.get("context_patch")
        if isinstance(patch, dict):
            patch.setdefault("subproject", "infographiste_ia")
            patch.setdefault("pipeline_doc", "docs/pipeline_assets_swg_godot.md")

    ok = bool(brief.get("ok", True)) and bool(probe.get("ok"))

    media_result = None
    if (not ok or ctx.get("pygmalion_generate")) and comfyui_enabled():
        gap_label = missing[0] if missing else (task.objective or "mmo asset")
        media_result = generate_asset_for_gap(str(gap_label))
        if media_result.get("ok"):
            ctx["comfyui_images"] = media_result.get("images")

    return {
        "kind": "infographiste_workflow",
        "ok": ok,
        "brief": brief,
        "probe": probe,
        "action_proposal": proposal_payload,
        "subproject": "infographiste_ia",
        "persona": "Pygmalion",
        "comfyui_probe": probe_comfyui() if comfyui_enabled() else None,
        "comfyui_generation": media_result,
    }


def resolve_infographiste_workflow(task: TeamTask) -> bool:
    return _is_infographiste_track(task)
