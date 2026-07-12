"""Workflow dev_game — jalon M9 Scrapaltai carte + minimap (Prime Client 2D)."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.human_summary import format_validation_summary
from team.m9_map_probe import (
    audit_m9_full_readiness,
    audit_m9a_readiness,
    audit_m9b_readiness,
    audit_m9c_readiness,
)
from team.m9_remediation import try_m9a_auto_remediate
from team.iris_gdscript_forge import forge_from_m9_probes, iris_forge_enabled
from team.iris_llm_forge import forge_with_llm_and_smoke, iris_llm_forge_enabled
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]

_TRACK_ALIASES = {
    "m9": "m9_full",
    "m9_full": "m9_full",
    "m9a": "m9a",
    "m9b": "m9b",
    "m9c": "m9c",
    "scrapaltai": "m9a",
    "minimap": "m9b",
    "planet_map": "m9c",
    "carte_m": "m9c",
}


def _normalize_track(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _TRACK_ALIASES.get(key, key)


def _detect_track(task: TeamTask) -> str | None:
    ctx = task.context
    raw = ctx.get("m9_track") or ctx.get("m9_map_track")
    if raw:
        return _normalize_track(str(raw))
    text = (task.objective or "").lower()
    if re.search(r"\b(m9c|carte.?m|planet.?map|waypoint)\b", text):
        return "m9c"
    if re.search(r"\b(m9b|minimap|mini.?map)\b", text):
        return "m9b"
    if re.search(r"\b(m9a|scrapaltai|planète|planete.?entière)\b", text):
        return "m9a"
    if re.search(r"\b(m9|jalon.?m9|map.?minimap)\b", text):
        return "m9_full"
    return None


def _run_track_probes(track: str) -> list[dict[str, object]]:
    if track == "m9a":
        return [audit_m9a_readiness()]
    if track == "m9b":
        return [audit_m9b_readiness()]
    if track == "m9c":
        return [audit_m9c_readiness()]
    if track == "m9_full":
        return [audit_m9_full_readiness()]
    return [audit_m9_full_readiness()]


def _forge_objective(task: TeamTask, track: str, probes: list[dict[str, object]]) -> str:
    gaps: list[str] = []
    for p in probes:
        if p.get("skipped"):
            continue
        if not p.get("ok"):
            nested = p.get("probes")
            if isinstance(nested, list):
                for sub in nested:
                    if not sub.get("ok"):
                        sg = sub.get("gaps") or []
                        if sg:
                            gaps.append(str(sg[0]))
            else:
                sg = p.get("gaps") or []
                if sg:
                    gaps.append(str(sg[0]))
                elif p.get("hint"):
                    gaps.append(str(p["hint"]))
    prefixes = {
        "m9a": "M9a Scrapaltai — texture planète + POI sync + pipeline export Godot",
        "m9b": "M9b minimap HUD style SWG — SubViewport coin écran",
        "m9c": "M9c carte planétaire M + waypoints + locations tree",
        "m9_full": "M9 complet — Scrapaltai 2D + minimap + carte M",
    }
    prefix = prefixes.get(track, prefixes["m9_full"])
    if gaps:
        return f"{prefix} — corriger: {gaps[0]}"
    return f"{prefix} — {task.objective}"


def _should_iris_forge(task: TeamTask) -> bool:
    if not iris_forge_enabled():
        return False
    ctx = task.context
    if ctx.get("iris_forge") or ctx.get("forge_gdscript"):
        return True
    if task.role == "dev_godot":
        return True
    if str(ctx.get("godot_dev_persona") or "").lower() == "iris":
        return True
    return False


def execute_m9_map_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    track = _detect_track(task) or "m9_full"
    ctx = dict(task.context)
    ctx.setdefault("m9_track", track)
    ctx.setdefault("subproject", "prime_client_2d")
    ctx.setdefault("dev_game_focus", True)

    remediation: dict[str, object] | None = None
    if track in ("m9a", "m9_full"):
        remediation = try_m9a_auto_remediate()

    probes = _run_track_probes(track)
    if remediation and remediation.get("attempted") and remediation.get("ok"):
        probes = _run_track_probes(track)
    failed: list[dict[str, object]] = []
    for p in probes:
        if p.get("skipped"):
            continue
        if not p.get("ok"):
            failed.append(p)
            nested = p.get("probes")
            if isinstance(nested, list):
                failed.extend([s for s in nested if not s.get("ok")])

    ok = len(failed) == 0
    forged = _forge_objective(task, track, probes)

    brief_ctx = {
        **ctx,
        "project_pm": {
            "include_plan": True,
            "scope": "game_dev",
            "subproject": "prime_client_2d",
            "exclude_sandbox_mmmorpg": True,
        },
        "subprojects_focus": ["prime_client_2d", "client_godot"],
        "m9_track": track,
    }
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=brief_ctx,
    )

    proposal_payload = None
    prop = propose_action_from_text(forged, ctx)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = f"team_m9_{track}"
        proposal_payload.setdefault(
            "summary",
            f"Jalon M9 {track} — prototype Prime Client 2D (revue humaine avant merge Godot)",
        )

    human_summary = format_validation_summary(
        title=f"Dédale — jalon M9 ({track})",
        probes=probes,
        forge_note=(proposal_payload or {}).get("summary") if proposal_payload else None,
        checklist=[
            "Preset « M9 planète » pour texture Scrapaltai + POI sync",
            "Preset « M9 minimap » ou « M9 carte M » pour HUD SWG",
            "Doc docs/jalon_m9_scrapaltai_map_minimap.md",
        ],
    )

    iris_forge_result = None
    iris_llm_forge_result = None
    if not ok and _should_iris_forge(task):
        persona = str(ctx.get("godot_dev_persona") or "iris").lower()
        if iris_llm_forge_enabled() or ctx.get("iris_forge_llm"):
            iris_llm_forge_result = forge_with_llm_and_smoke(
                _collect_gaps_for_forge(probes),
                task_id=task.id,
                track=track,
                persona=persona,
                auto_apply=bool(ctx.get("iris_forge_auto_apply")),
            )
            iris_forge_result = iris_llm_forge_result.get("template_forge")
        else:
            iris_forge_result = forge_from_m9_probes(
                probes,
                task_id=task.id,
                track=track,
                persona=persona,
                auto_apply=bool(ctx.get("iris_forge_auto_apply")),
            )
            if iris_forge_result:
                iris_forge_result = iris_forge_result.to_dict()
        forge_payload = iris_llm_forge_result or (iris_forge_result if isinstance(iris_forge_result, dict) else None)
        if forge_payload and (forge_payload.get("patches") or forge_payload.get("template_forge")):
            patches_n = len((iris_forge_result or {}).get("patches") or [])
            if iris_llm_forge_result:
                patches_n = len((iris_llm_forge_result.get("template_forge") or {}).get("patches") or [])
            patch_note = f"Iris forge — {patches_n} patch(es)"
            if iris_llm_forge_result:
                patch_note += f" · smoke={'OK' if iris_llm_forge_result.get('smoke_ok') else 'KO'}"
            human_summary = format_validation_summary(
                title=f"Iris — forge M9 ({track})",
                probes=probes,
                forge_note=patch_note,
                checklist=[
                    f"Staging : {(iris_forge_result or {}).get('staging_dir', 'n/a')}",
                    "LBG_IRIS_FORGE_AUTO_APPLY=1 + smoke OK pour apply",
                    "Doc docs/jalon_iris_forge_gdscript.md",
                ],
            )


    return {
        "kind": "m9_map_workflow",
        "ok": ok,
        "track": track,
        "probes": probes,
        "brief": brief,
        "action_proposal": proposal_payload,
        "subproject": "prime_client_2d",
        "failed_count": len(failed),
        "human_summary": human_summary,
        "remediation": remediation,
        "iris_forge": iris_forge_result if isinstance(iris_forge_result, dict) else (iris_forge_result.to_dict() if iris_forge_result else None),
        "iris_llm_forge": iris_llm_forge_result,
    }


def _collect_gaps_for_forge(probes: list[dict[str, object]]) -> list[str]:
    from team.iris_gdscript_forge import _collect_gaps_from_probes

    return _collect_gaps_from_probes(probes)  # type: ignore[arg-type]


def resolve_m9_map_workflow(task: TeamTask) -> bool:
    track = _detect_track(task)
    if track in ("m9a", "m9b", "m9c", "m9_full"):
        return True
    ctx = task.context
    return bool(ctx.get("m9_track") or ctx.get("m9_map_track"))
