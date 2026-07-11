"""Workflow dev_game — pistes M3 SOE, M5 play, ZB-0 ZoneBridge."""

from __future__ import annotations

import re
from typing import Callable

from services.action_proposal import propose_action_from_text

from team.godot_soe_probe import probe_soe_m3_login, probe_soe_m3_zone, probe_soe_m5_play
from team.human_summary import format_validation_summary
from team.lbg_ws2_audit import audit_lbg_ws2_readiness, audit_zb0_readiness
from team.models import TeamTask

Dispatcher = Callable[..., dict[str, object]]

_TRACK_ALIASES = {
    "soe_m3": "soe_m3",
    "m3": "soe_m3",
    "soe_m5": "soe_m5",
    "m5": "soe_m5",
    "zb0": "zb0",
    "zone_bridge": "zb0",
    "client_live": "client_live",
}


def _normalize_track(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _TRACK_ALIASES.get(key, key)


def _detect_track(task: TeamTask) -> str | None:
    ctx = task.context
    raw = ctx.get("godot_track") or ctx.get("godot_client_track")
    if raw:
        return _normalize_track(str(raw))
    text = (task.objective or "").lower()
    if re.search(r"\b(soe.?m5|m5.?play|zqsd|prime_controller)\b", text):
        return "soe_m5"
    if re.search(r"\b(soe.?m3|soe.?live|soe.?udp|soe_handshake)\b", text):
        return "soe_m3"
    if re.search(r"\b(zb-?0|zone.?bridge|lbgzonebridge)\b", text):
        return "zb0"
    if re.search(r"\b(client.?live|m3.?m5.?zb)\b", text):
        return "client_live"
    return None


def _run_track_probes(track: str) -> list[dict[str, object]]:
    if track == "soe_m3":
        return [probe_soe_m3_login(), probe_soe_m3_zone()]
    if track == "soe_m5":
        return [probe_soe_m5_play()]
    if track == "zb0":
        return [audit_zb0_readiness()]
    if track == "client_live":
        return [
            probe_soe_m3_login(),
            probe_soe_m3_zone(),
            probe_soe_m5_play(),
            audit_zb0_readiness(),
            audit_lbg_ws2_readiness(),
        ]
    return [audit_lbg_ws2_readiness()]


def _forge_objective(task: TeamTask, track: str, probes: list[dict[str, object]]) -> str:
    gaps: list[str] = []
    for p in probes:
        if p.get("skipped"):
            continue
        if not p.get("ok"):
            t = p.get("track") or "probe"
            hint = p.get("hint") or (p.get("gaps") or [None])[0] if isinstance(p.get("gaps"), list) else None
            gaps.append(str(hint or t))
    base = task.objective
    if track == "soe_m3":
        prefix = "prototype SOE M3 login+zone Godot Prime"
    elif track == "soe_m5":
        prefix = "prototype SOE M5 play ZQSD prime_controller"
    elif track == "zb0":
        prefix = "prototype ZB-0 LbgZoneBridge C++ hook ZoneServer lecture seule"
    else:
        prefix = "prototype client Godot live M3/M5/ZB-0"
    if gaps:
        return f"{prefix} — corriger: {gaps[0]}"
    return f"{prefix} — {base}"


def execute_godot_client_tracks_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    track = _detect_track(task)
    if not track:
        track = "client_live"
    ctx = dict(task.context)
    ctx.setdefault("godot_track", track)
    ctx.setdefault("subproject", "client_godot")
    ctx.setdefault("dev_game_focus", True)

    probes = _run_track_probes(track)
    failed = [p for p in probes if not p.get("ok") and not p.get("skipped")]
    ok = len(failed) == 0

    brief_ctx = {
        **ctx,
        "project_pm": {
            "include_plan": True,
            "scope": "game_dev",
            "subproject": "client_godot",
            "exclude_sandbox_mmmorpg": True,
        },
        "subprojects_focus": ["client_godot", "core3_prime"],
        "godot_track": track,
    }
    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=brief_ctx,
    )

    forge_objective = _forge_objective(task, track, probes)
    proposal_payload = None
    prop = propose_action_from_text(forge_objective, ctx)
    if prop.proposal is not None:
        proposal_payload = prop.proposal.model_dump()
        proposal_payload["source"] = f"team_godot_{track}"
        proposal_payload.setdefault(
            "summary",
            f"Piste {track} — prototype OpenGame (revue humaine avant build Core3/Godot)",
        )

    human_summary = format_validation_summary(
        title=f"Dédale — piste client Godot ({track})",
        probes=probes,
        forge_note=(proposal_payload or {}).get("summary") if proposal_payload else None,
        checklist=[
            "Preset « Valider client » pour checklist Godot visuelle",
            "Preset « Plan build ZB-0 » ou « Compiler Core3 » si gaps C++",
        ],
    )

    return {
        "kind": "godot_client_tracks_workflow",
        "ok": ok,
        "track": track,
        "probes": probes,
        "brief": brief,
        "action_proposal": proposal_payload,
        "subproject": "client_godot",
        "failed_count": len(failed),
        "human_summary": human_summary,
    }


def resolve_godot_client_tracks_workflow(task: TeamTask) -> bool:
    track = _detect_track(task)
    return track in ("soe_m3", "soe_m5", "zb0", "client_live")
