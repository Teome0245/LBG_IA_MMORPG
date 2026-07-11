"""Suivi automatique après échec superviseur Godot (PM + dev_game + player_ia)."""

from __future__ import annotations

import os
import time
from typing import Any

from team import store as team_store
from team.models import TeamTask


def followup_enabled() -> bool:
    return os.environ.get("LBG_TEAM_GODOT_FOLLOWUP_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def followup_actor_id() -> str:
    return os.environ.get("LBG_TEAM_GODOT_FOLLOWUP_ACTOR_ID", "system:team_godot_followup").strip()


def auto_run_followup_enabled() -> bool:
    return os.environ.get("LBG_TEAM_GODOT_FOLLOWUP_AUTO_RUN", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def auto_run_followup_tasks(task_ids: list[str]) -> list[dict[str, object]]:
    if not auto_run_followup_enabled():
        return []
    from team import roles as team_roles

    results: list[dict[str, object]] = []
    for tid in task_ids:
        task = team_store.get_task(tid)
        if task is None or task.status != "queued":
            continue
        if task.role not in ("pm", "dev_game", "player_ia"):
            continue
        ran = team_roles.run_task(tid)
        if ran is not None:
            results.append({"task_id": tid, "role": ran.role, "status": ran.status})
    return results


def maybe_spawn_after_godot_failure(task: TeamTask) -> list[str]:
    if not followup_enabled():
        return []
    if task.status != "failed":
        return []
    if task.context.get("_godot_followup_spawned"):
        return []
    result = task.result if isinstance(task.result, dict) else {}
    if result.get("kind") not in ("godot_supervisor", "godot_client_workflow", "godot_client_tracks_workflow"):
        return []

    tracks = result.get("tracks") if isinstance(result.get("tracks"), list) else []
    probes = result.get("probes") if isinstance(result.get("probes"), list) else []
    combined = tracks + probes
    sidecar_failed = any(
        isinstance(t, dict) and t.get("track") in ("sidecar_m1", "godot_mirror_m1") and not t.get("ok")
        for t in combined
    )
    soe_failed = any(
        isinstance(t, dict) and str(t.get("track", "")).startswith("soe_") and not t.get("ok") and not t.get("skipped")
        for t in combined
    )
    zb_failed = any(
        isinstance(t, dict) and t.get("track") == "zb0_readiness" and not t.get("ok")
        for t in combined
    )
    ws2_gaps = []
    for t in combined:
        if isinstance(t, dict) and t.get("track") == "lbg_ws2_readiness":
            ws2_gaps = list(t.get("gaps") or [])
        if isinstance(t, dict) and t.get("track") == "zb0_readiness":
            ws2_gaps.extend(list(t.get("gaps") or [])[:2])

    created_ids: list[str] = []
    parent_ref = {"parent_task_id": task.id, "parent_trace_id": task.trace_id}

    pm_obj = os.environ.get(
        "LBG_TEAM_GODOT_FOLLOWUP_PM_OBJECTIVE",
        f"Brief Godot/Core3 — triage superviseur client (parent={task.id})",
    ).strip()
    pm = team_store.create_task(
        role="pm",
        objective=pm_obj,
        actor_id=followup_actor_id(),
        priority="high" if sidecar_failed else "normal",
        context={
            **parent_ref,
            "_godot_followup": True,
            "godot_failure_summary": _summarize(result),
            "reunification_brief": True,
        },
    )
    created_ids.append(pm.id)

    dev_obj = os.environ.get(
        "LBG_TEAM_GODOT_FOLLOWUP_DEV_OBJECTIVE",
        (
            f"Godot — corriger lacunes client live M3/M5/ZB-0 (parent {task.id})"
            + (f" — gaps: {', '.join(ws2_gaps[:3])}" if ws2_gaps else "")
            + (" — SOE KO" if soe_failed else "")
            + (" — ZB-0 KO" if zb_failed else "")
        ),
    ).strip()
    dev_ctx: dict[str, object] = {
        **parent_ref,
        "_godot_followup": True,
        "godot_failure_summary": _summarize(result),
    }
    if soe_failed and not zb_failed:
        dev_ctx["godot_track"] = "soe_m3" if any(
            isinstance(t, dict) and t.get("track") == "soe_m3_zone" and not t.get("ok") for t in combined
        ) else "soe_m5"
    elif zb_failed:
        dev_ctx["godot_track"] = "zb0"
    else:
        dev_ctx["godot_track"] = "client_live"
    dev = team_store.create_task(
        role="dev_game",
        objective=dev_obj,
        actor_id=followup_actor_id(),
        priority="high",
        context=dev_ctx,
    )
    created_ids.append(dev.id)

    if sidecar_failed:
        pia = team_store.create_task(
            role="player_ia",
            objective="Re-sonde joueurs IA Prime après échec superviseur Godot",
            actor_id=followup_actor_id(),
            priority="high",
            context={**parent_ref, "_godot_followup": True, "player_ia_mode": "probe"},
        )
        created_ids.append(pia.id)

    team_store.update_task(
        task.id,
        context_patch={
            "_godot_followup_spawned": True,
            "_godot_followup_task_ids": created_ids,
            "_godot_followup_ts": time.time(),
        },
    )
    return created_ids


def _summarize(result: dict[str, Any]) -> dict[str, Any]:
    tracks = result.get("tracks") if isinstance(result.get("tracks"), list) else []
    probes = result.get("probes") if isinstance(result.get("probes"), list) else []
    combined = tracks + probes
    failed = [t.get("track") for t in combined if isinstance(t, dict) and not t.get("ok") and not t.get("skipped")]
    return {
        "kind": result.get("kind"),
        "track": result.get("track"),
        "failed_tracks": failed,
        "sidecar_ok": result.get("sidecar_ok"),
    }
