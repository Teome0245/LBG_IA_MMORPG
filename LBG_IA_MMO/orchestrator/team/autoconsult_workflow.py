"""Round autoconsultation — Thémis orchestre les spécialistes (style Fable)."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from team import store as team_store
from team.agent_registry import list_agents_summary
from team.human_summary import format_validation_summary
from team.infographiste_probe import probe_infographiste_assets
from team.m9_map_probe import audit_m9_full_readiness
from team.m9_remediation import try_m9a_auto_remediate
from team.godot_supervisor import execute_godot_supervisor
from team.models import TeamTask
from team.subprojects import list_subprojects

Dispatcher = Callable[..., dict[str, object]]


def autoconsult_enabled() -> bool:
    return os.environ.get("LBG_TEAM_AUTOCONSULT_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def followup_auto_run() -> bool:
    return os.environ.get("LBG_TEAM_AUTOCONSULT_FOLLOWUP_AUTO_RUN", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _qa_probe() -> dict[str, Any]:
    from team import roles as team_roles

    script = os.environ.get("LBG_TEAM_QA_SMOKE_SCRIPT", "").strip()
    if script and os.path.isfile(script):
        return team_roles._run_qa_smoke_script()
    targets = team_roles._qa_health_targets()
    checks = []
    for url in targets[:4]:
        try:
            import httpx

            r = httpx.get(url, timeout=5.0)
            checks.append({"url": url, "ok": r.status_code == 200, "status": r.status_code})
        except Exception as exc:
            checks.append({"url": url, "ok": False, "error": str(exc)})
    ok = all(c.get("ok") for c in checks) if checks else False
    return {"track": "qa_health", "ok": ok, "checks": checks}


def _ops_probe() -> dict[str, Any]:
    from team import roles as team_roles

    orch = team_roles._orchestrator_url()
    try:
        import httpx

        r = httpx.get(f"{orch}/healthz", timeout=5.0)
        return {"track": "ops_orchestrator", "ok": r.status_code == 200, "url": f"{orch}/healthz"}
    except Exception as exc:
        return {"track": "ops_orchestrator", "ok": False, "error": str(exc)}


def _iris_probe() -> dict[str, Any]:
    remediation = try_m9a_auto_remediate()
    probe = audit_m9_full_readiness()
    return {"track": "iris_m9", "remediation": remediation, **probe}


def _pygmalion_probe() -> dict[str, Any]:
    fake = TeamTask(
        id="autoconsult",
        role="dev_game",
        objective="autoconsult infographiste",
        context={"infographiste_ia": True},
    )
    return probe_infographiste_assets(fake)


def _hermes_probe() -> dict[str, Any]:
    fake = TeamTask(
        id="autoconsult",
        role="dev_godot",
        objective="autoconsult hermes soe gateway",
        context={"godot_mode": "client_live"},
    )
    out = execute_godot_supervisor(fake)
    tracks = out.get("tracks") or []
    gaps: list[str] = []
    for t in tracks:
        if not isinstance(t, dict) or t.get("ok") or t.get("skipped"):
            continue
        label = str(t.get("track") or "hermes")
        detail = t.get("hint") or t.get("error") or "échec sonde"
        gaps.append(f"{label}: {detail}")
    return {"track": "hermes_soe", "ok": bool(out.get("ok")), "gaps": gaps, "probes": tracks}


def _collect_gaps(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for p in probes:
        track = str(p.get("track") or "unknown")
        owner = (
            "iris"
            if "m9" in track or "iris" in track
            else "hermes"
            if any(k in track for k in ("hermes", "soe", "sidecar", "mirror", "lbg_ws", "zb0", "gateway"))
            else "argus"
            if track.startswith("qa")
            else "hephaistos"
            if track.startswith("ops")
            else "pygmalion"
            if "infograph" in track
            else "pm"
        )
        if p.get("ok"):
            continue
        for g in p.get("gaps") or []:
            gaps.append({"owner": owner, "track": track, "gap": str(g)})
        nested = p.get("probes")
        if isinstance(nested, list):
            for sub in nested:
                if isinstance(sub, dict) and not sub.get("ok"):
                    for g in sub.get("gaps") or []:
                        gaps.append({"owner": owner, "track": sub.get("track", track), "gap": str(g)})
        if not p.get("gaps") and not p.get("ok") and p.get("hint"):
            gaps.append({"owner": owner, "track": track, "gap": str(p["hint"])})
        if not p.get("gaps") and not p.get("ok") and p.get("error"):
            gaps.append({"owner": owner, "track": track, "gap": str(p["error"])})
    return gaps


def _spawn_followups(task: TeamTask, gaps: list[dict[str, Any]]) -> list[str]:
    if not gaps or not followup_auto_run():
        return []
    actor = os.environ.get("LBG_TEAM_AUTOCONSULT_FOLLOWUP_ACTOR_ID", "system:team_autoconsult").strip()
    created: list[str] = []
    parent = {"parent_task_id": task.id, "autoconsult_round": True}

    by_owner: dict[str, list[str]] = {}
    for item in gaps[:12]:
        by_owner.setdefault(str(item["owner"]), []).append(str(item["gap"]))

    if by_owner.get("iris"):
        t = team_store.create_task(
            role="dev_godot",
            objective=f"Iris — corriger M9 : {by_owner['iris'][0]}",
            actor_id=actor,
            context={**parent, "godot_dev_persona": "iris", "godot_dev_track": "m9_full", "subproject": "godot_iris", "iris_forge": True},
        )
        created.append(t.id)
    if by_owner.get("hermes"):
        t = team_store.create_task(
            role="dev_godot",
            objective=f"Hermès — SOE/gateway : {by_owner['hermes'][0]}",
            actor_id=actor,
            context={**parent, "godot_dev_persona": "hermes", "godot_dev_track": "client_live", "subproject": "godot_hermes"},
        )
        created.append(t.id)
    if by_owner.get("pygmalion"):
        t = team_store.create_task(
            role="dev_game",
            objective=f"Pygmalion — assets : {by_owner['pygmalion'][0]}",
            actor_id=actor,
            context={**parent, "infographiste_ia": True, "subproject": "infographiste_ia"},
        )
        created.append(t.id)
    if by_owner.get("hephaistos"):
        t = team_store.create_task(
            role="ops",
            objective=f"Héphaïstos — infra : {by_owner['hephaistos'][0]}",
            actor_id=actor,
            context={**parent, "m9_ops_sync": True, "ops_kind": "m9_prime_sync"},
        )
        created.append(t.id)
    if by_owner.get("argus"):
        t = team_store.create_task(
            role="qa",
            objective=f"Argus — re-smoke : {by_owner['argus'][0]}",
            actor_id=actor,
            context={**parent, "godot_validation": True},
        )
        created.append(t.id)

    return created


def execute_autoconsult_workflow(task: TeamTask, dispatch: Dispatcher) -> dict[str, object]:
    if not autoconsult_enabled():
        return {"kind": "autoconsult_workflow", "ok": True, "skipped": True, "reason": "LBG_TEAM_AUTOCONSULT_ENABLED=0"}

    probes: list[dict[str, Any]] = [
        _qa_probe(),
        _ops_probe(),
        _iris_probe(),
        _hermes_probe(),
        _pygmalion_probe(),
    ]

    gaps = _collect_gaps(probes)
    ok = len(gaps) == 0

    brief = dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective or "Round autoconsultation équipe studio",
        context={
            "reunification_brief": True,
            "pm_include_plan": True,
            "pm_include_structure": True,
            "subprojects": list_subprojects(),
            "autoconsult_probes": probes,
            "autoconsult_gaps": gaps[:20],
            "agents_roster": list_agents_summary(),
        },
    )

    followup_ids = _spawn_followups(task, gaps)
    ran_followups: list[dict[str, object]] = []
    if followup_ids and followup_auto_run():
        from team import roles as team_roles

        for fid in followup_ids:
            ft = team_store.get_task(fid)
            if ft and ft.status == "queued":
                result = team_roles.run_task(fid)
                if result:
                    ran_followups.append({"task_id": fid, "role": result.role, "status": result.status})

    human_summary = format_validation_summary(
        title="Thémis — round autoconsultation (Fable)",
        probes=probes,
        checklist=[
            f"{len(gaps)} gap(s) détecté(s)",
            f"{len(followup_ids)} followup(s) spawné(s)",
            "Doc docs/vision_equipe_fable_autoconsultation.md",
        ],
    )

    return {
        "kind": "autoconsult_workflow",
        "ok": ok,
        "probes": probes,
        "gaps": gaps,
        "gaps_count": len(gaps),
        "brief": brief,
        "followup_task_ids": followup_ids,
        "followup_ran": ran_followups,
        "agents_count": len(list_agents_summary()),
        "human_summary": human_summary,
        "timestamp": time.time(),
    }


def resolve_autoconsult_workflow(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("autoconsult_round") or ctx.get("autoconsult"):
        return True
    text = (task.objective or "").lower()
    return bool(
        any(k in text for k in ("autoconsult", "autoconsultation", "round fable", "round équipe", "round equipe"))
    )
