"""Suivi automatique après échec jalon M9 — PM + dev_game ciblé + ops sync + infographiste."""

from __future__ import annotations

import os
import time
from typing import Any

from team import store as team_store
from team.models import TeamTask


def followup_enabled() -> bool:
    return os.environ.get("LBG_TEAM_M9_FOLLOWUP_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def followup_actor_id() -> str:
    return os.environ.get("LBG_TEAM_M9_FOLLOWUP_ACTOR_ID", "system:team_m9_followup").strip()


def auto_run_followup_enabled() -> bool:
    return os.environ.get("LBG_TEAM_M9_FOLLOWUP_AUTO_RUN", "1").strip().lower() in ("1", "true", "yes", "on")


def auto_run_followup_tasks(task_ids: list[str]) -> list[dict[str, object]]:
    if not auto_run_followup_enabled():
        return []
    from team import roles as team_roles

    results: list[dict[str, object]] = []
    for tid in task_ids:
        task = team_store.get_task(tid)
        if task is None or task.status != "queued":
            continue
        if task.role not in ("pm", "dev_godot", "dev_game", "ops"):
            continue
        ran = team_roles.run_task(tid)
        if ran is not None:
            results.append({"task_id": tid, "role": ran.role, "status": ran.status})
    return results


def _collect_gaps(result: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    for probe in result.get("probes") or []:
        if not isinstance(probe, dict):
            continue
        nested = probe.get("probes")
        if isinstance(nested, list):
            for sub in nested:
                if isinstance(sub, dict) and not sub.get("ok"):
                    gaps.extend(list(sub.get("gaps") or []))
        elif not probe.get("ok"):
            gaps.extend(list(probe.get("gaps") or []))
    return gaps


def _next_track(current: str, gaps: list[str]) -> str:
    text = " ".join(gaps).lower()
    if current == "m9a" or any(k in text for k in ("export", "sync", "poi", "texture", "maps_dir")):
        if any(k in text for k in ("minimap", "m9b")):
            return "m9b"
        return "m9a"
    if current == "m9b" or "minimap" in text:
        return "m9b"
    if current == "m9c" or any(k in text for k in ("planet_map", "waypoint", "carte")):
        return "m9c"
    return "m9_full"


def maybe_spawn_after_m9_failure(task: TeamTask) -> list[str]:
    if not followup_enabled():
        return []
    if task.status != "failed":
        return []
    if task.context.get("_m9_followup_spawned"):
        return []

    result = task.result if isinstance(task.result, dict) else {}
    kind = result.get("kind")
    track = str(result.get("track") or result.get("godot_dev_track") or task.context.get("m9_track") or "")
    if kind not in ("m9_map_workflow", "godot_dev_workflow"):
        return []
    if kind == "godot_dev_workflow" and not track.startswith("m9"):
        return []

    track = str(result.get("track") or task.context.get("m9_track") or "m9_full")
    gaps = _collect_gaps(result)
    next_track = _next_track(track, gaps)
    parent_ref = {"parent_task_id": task.id, "parent_trace_id": task.trace_id}
    created_ids: list[str] = []

    pm = team_store.create_task(
        role="pm",
        objective=f"Brief M9 Scrapaltai — triage {track} (parent={task.id})",
        actor_id=followup_actor_id(),
        priority="normal",
        context={
            **parent_ref,
            "_m9_followup": True,
            "reunification_brief": True,
            "m9_failure_gaps": gaps[:8],
            "subprojects_focus": ["prime_client_2d"],
        },
    )
    created_ids.append(pm.id)

    dev = team_store.create_task(
        role="dev_godot",
        objective=(
            f"Iris M9 {next_track} — corriger gaps carte/minimap"
            + (f" : {gaps[0]}" if gaps else "")
        ),
        actor_id=followup_actor_id(),
        priority="high",
        context={
            **parent_ref,
            "_m9_followup": True,
            "godot_dev_persona": "iris",
            "godot_dev_track": next_track,
            "m9_track": next_track,
            "subproject": "godot_iris",
            "dev_godot_focus": True,
            "m9_failure_gaps": gaps[:8],
        },
    )
    created_ids.append(dev.id)

    if any("texture" in g.lower() or "svg" in g.lower() for g in gaps):
        art = team_store.create_task(
            role="dev_game",
            objective="Infographiste — enrichir texture Scrapaltai tatooine.svg (M9a-1)",
            actor_id=followup_actor_id(),
            priority="normal",
            context={
                **parent_ref,
                "_m9_followup": True,
                "infographiste_ia": True,
                "subproject": "infographiste_ia",
            },
        )
        created_ids.append(art.id)

    if any("maps_dir" in g.lower() or "prime client absent" in g.lower() for g in gaps):
        ops = team_store.create_task(
            role="ops",
            objective="Sync prime-client assets vers VM core pour sondes M9 (sync_prime_client_assets_vm.sh)",
            actor_id=followup_actor_id(),
            priority="normal",
            context={
                **parent_ref,
                "_m9_followup": True,
                "m9_ops_sync": True,
                "subproject": "prime_client_2d",
            },
        )
        created_ids.append(ops.id)

    team_store.update_task(
        task.id,
        context_patch={
            "_m9_followup_spawned": True,
            "_m9_followup_task_ids": created_ids,
            "_m9_followup_ts": time.time(),
        },
    )
    return created_ids
