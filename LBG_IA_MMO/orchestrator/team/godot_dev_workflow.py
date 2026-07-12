"""Workflow dev_godot — personas Iris (2D/UI) et Hermès (réseau/SOE)."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.godot_client_tracks_workflow import execute_godot_client_tracks_workflow
from team.human_summary import format_validation_summary
from team.m9_map_workflow import execute_m9_map_workflow
from team.m9_map_probe import audit_m9_full_readiness, audit_m9a_readiness, audit_m9b_readiness, audit_m9c_readiness
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]

_PERSONA_ALIASES = {
    "iris": "iris",
    "iris_2d": "iris",
    "2d": "iris",
    "hermes": "hermes",
    "hermes_net": "hermes",
    "network": "hermes",
    "soe": "hermes",
}

_TRACK_ALIASES = {
    "m9": "m9_full",
    "m9a": "m9a",
    "m9b": "m9b",
    "m9c": "m9c",
    "m9_full": "m9_full",
    "soe_m3": "soe_m3",
    "soe_m5": "soe_m5",
    "zb0": "zb0",
    "zb1": "zb1",
    "client_live": "client_live",
    "iris_full": "iris_full",
    "hermes_full": "hermes_full",
    "full": "full",
}


def _normalize_persona(raw: str) -> str:
    return _PERSONA_ALIASES.get((raw or "").strip().lower(), (raw or "iris").lower())


def _normalize_track(raw: str) -> str:
    return _TRACK_ALIASES.get((raw or "").strip().lower(), (raw or "iris_full").lower())


def _detect_persona(task: TeamTask) -> str:
    ctx = task.context
    raw = ctx.get("godot_dev_persona") or ctx.get("godot_persona")
    if raw:
        return _normalize_persona(str(raw))
    text = (task.objective or "").lower()
    if re.search(r"\b(hermes|soe|gateway|udp|lbg-ws|zb-?\d)\b", text):
        return "hermes"
    if re.search(r"\b(iris|2d|minimap|carte|m9|scrapaltai|waypoint|ui godot)\b", text):
        return "iris"
    return "iris"


def _detect_track(task: TeamTask, persona: str) -> str:
    ctx = task.context
    raw = ctx.get("godot_dev_track") or ctx.get("m9_track") or ctx.get("godot_track")
    if raw:
        return _normalize_track(str(raw))
    text = (task.objective or "").lower()
    if persona == "hermes":
        if re.search(r"\bzb-?1\b", text):
            return "zb1"
        if re.search(r"\bzb-?0\b", text):
            return "zb0"
        if re.search(r"\bm5\b", text):
            return "soe_m5"
        if re.search(r"\bm3\b", text):
            return "soe_m3"
        return "client_live"
    if re.search(r"\bm9c\b", text):
        return "m9c"
    if re.search(r"\bm9b\b", text):
        return "m9b"
    if re.search(r"\bm9a\b", text):
        return "m9a"
    if re.search(r"\bm9\b", text):
        return "m9_full"
    return "iris_full"


def _iris_probes(track: str) -> list[dict[str, object]]:
    if track == "m9a":
        return [audit_m9a_readiness()]
    if track == "m9b":
        return [audit_m9b_readiness()]
    if track == "m9c":
        return [audit_m9c_readiness()]
    if track == "m9_full":
        return [audit_m9_full_readiness()]
    return [audit_m9_full_readiness()]


def execute_godot_dev_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    persona = _detect_persona(task)
    track = _detect_track(task, persona)
    ctx = dict(task.context)
    ctx.setdefault("godot_dev_persona", persona)
    ctx.setdefault("godot_dev_track", track)
    ctx.setdefault("subproject", "godot_iris" if persona == "iris" else "godot_hermes")
    ctx.setdefault("dev_godot_focus", True)

    # Délégation M9 / SOE aux workflows existants
    if persona == "iris" and track in ("m9a", "m9b", "m9c", "m9_full"):
        delegated = dict(task.context)
        delegated["m9_track"] = track
        delegated["subproject"] = "prime_client_2d"
        sub = TeamTask(
            id=task.id,
            role=task.role,
            objective=task.objective,
            actor_id=task.actor_id,
            context=delegated,
        )
        out = execute_m9_map_workflow(sub, dispatch)
        out["persona"] = "iris"
        out["godot_dev_track"] = track
        out["kind"] = "godot_dev_workflow"
        return out

    if persona == "hermes" and track in ("soe_m3", "soe_m5", "zb0", "zb1", "client_live"):
        delegated = dict(task.context)
        delegated["godot_track"] = track
        delegated["subproject"] = "client_godot"
        sub = TeamTask(
            id=task.id,
            role=task.role,
            objective=task.objective,
            actor_id=task.actor_id,
            context=delegated,
        )
        out = execute_godot_client_tracks_workflow(sub, dispatch)
        out["persona"] = "hermes"
        out["godot_dev_track"] = track
        out["kind"] = "godot_dev_workflow"
        return out

    probes = _iris_probes(track) if persona == "iris" else []
    failed = [p for p in probes if not p.get("ok") and not p.get("skipped")]
    ok = len(failed) == 0

    persona_label = "Iris" if persona == "iris" else "Hermès"
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context={
            **ctx,
            "project_pm": {"include_plan": True, "scope": "godot_dev", "subproject": ctx["subproject"]},
            "godot_dev_persona": persona,
        },
    )

    forged = task.objective if ok else f"{persona_label} — corriger: {(failed[0].get('gaps') or ['gap'])[0] if failed else 'gap'}"
    proposal_payload = None
    prop = propose_action_from_text(forged, ctx)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = f"team_godot_dev_{persona}_{track}"

    human_summary = format_validation_summary(
        title=f"{persona_label} — dev Godot ({track})",
        probes=probes,
        forge_note=(proposal_payload or {}).get("summary") if proposal_payload else None,
        checklist=[
            "Preset Iris M9 / Hermès SOE dans Pilot #/team",
            "Doc docs/jalon_equipe_godot_dev_ia.md",
        ],
    )

    return {
        "kind": "godot_dev_workflow",
        "ok": ok,
        "persona": persona,
        "track": track,
        "godot_dev_track": track,
        "probes": probes,
        "brief": brief,
        "action_proposal": proposal_payload,
        "subproject": ctx["subproject"],
        "failed_count": len(failed),
        "human_summary": human_summary,
    }


def resolve_godot_dev_workflow(task: TeamTask) -> bool:
    if task.role == "dev_godot":
        return True
    ctx = task.context
    return bool(ctx.get("godot_dev") or ctx.get("godot_dev_persona") or ctx.get("dev_godot_focus"))
