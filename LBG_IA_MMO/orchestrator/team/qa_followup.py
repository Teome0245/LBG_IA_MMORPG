"""Phase C — suivi automatique après échec d'une tâche QA (triage PM + ops optionnel)."""

from __future__ import annotations

import os
import time
from typing import Any

from team import store as team_store
from team.models import TeamTask


def followup_enabled() -> bool:
    return os.environ.get("LBG_TEAM_QA_FOLLOWUP_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def followup_actor_id() -> str:
    return os.environ.get("LBG_TEAM_QA_FOLLOWUP_ACTOR_ID", "system:team_qa_followup").strip()


def auto_run_pm_enabled() -> bool:
    return os.environ.get("LBG_TEAM_QA_FOLLOWUP_AUTO_RUN_PM", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def auto_run_followup_tasks(task_ids: list[str]) -> list[dict[str, object]]:
    """Exécute automatiquement les tâches PM de suivi (L1). Import paresseux pour éviter cycle roles↔qa_followup."""
    if not auto_run_pm_enabled():
        return []
    from team import roles as team_roles

    results: list[dict[str, object]] = []
    for tid in task_ids:
        task = team_store.get_task(tid)
        if task is None or task.role != "pm" or task.status != "queued":
            continue
        ran = team_roles.run_task(tid)
        if ran is not None:
            results.append({"task_id": tid, "role": ran.role, "status": ran.status})
    return results


def maybe_spawn_after_qa_failure(task: TeamTask) -> list[str]:
    """Crée des tâches de suivi si la QA a échoué. Retourne les ids créés."""
    if not followup_enabled():
        return []
    if task.role != "qa" or task.status != "failed":
        return []
    if task.context.get("_qa_followup_spawned"):
        return []

    result = task.result if isinstance(task.result, dict) else {}
    smoke = result.get("smoke_script") if isinstance(result.get("smoke_script"), dict) else {}
    smoke_failed = smoke.get("skipped") is not True and smoke.get("ok") is False

    created_ids: list[str] = []
    parent_ref = {"parent_task_id": task.id, "parent_trace_id": task.trace_id}

    pm_obj = os.environ.get(
        "LBG_TEAM_QA_FOLLOWUP_PM_OBJECTIVE",
        f"Triage échec QA — analyser résultat smoke/healthz et proposer prochaines actions (parent={task.id})",
    ).strip()
    pm = team_store.create_task(
        role="pm",
        objective=pm_obj,
        actor_id=followup_actor_id(),
        priority="high" if smoke_failed else "normal",
        context={**parent_ref, "_qa_followup": True, "qa_failure_summary": _summarize_failure(result)},
    )
    created_ids.append(pm.id)

    if smoke_failed:
        ops_obj = os.environ.get(
            "LBG_TEAM_QA_FOLLOWUP_OPS_OBJECTIVE",
            f"Sonde infra après échec smoke LAN (parent QA {task.id})",
        ).strip()
        ops = team_store.create_task(
            role="ops",
            objective=ops_obj,
            actor_id=followup_actor_id(),
            priority="high",
            context={
                **parent_ref,
                "_qa_followup": True,
            },
        )
        created_ids.append(ops.id)

        dev_obj = os.environ.get(
            "LBG_TEAM_QA_FOLLOWUP_DEV_OBJECTIVE",
            f"Analyser échec smoke — proposition correctif gameplay/infra hors sandbox mmmorpg (parent QA {task.id})",
        ).strip()
        dev = team_store.create_task(
            role="dev_game",
            objective=dev_obj,
            actor_id=followup_actor_id(),
            priority="high",
            context={
                **parent_ref,
                "_qa_followup": True,
                "qa_failure_summary": _summarize_failure(result),
            },
        )
        created_ids.append(dev.id)

    team_store.update_task(
        task.id,
        context_patch={
            "_qa_followup_spawned": True,
            "_qa_followup_task_ids": created_ids,
            "_qa_followup_ts": time.time(),
        },
    )
    return created_ids


def _summarize_failure(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("health_checks")
    failed_urls = []
    if isinstance(checks, list):
        for c in checks:
            if isinstance(c, dict) and not c.get("ok"):
                failed_urls.append(c.get("url"))
    smoke = result.get("smoke_script") if isinstance(result.get("smoke_script"), dict) else {}
    return {
        "kind": result.get("kind"),
        "failed_health_urls": failed_urls,
        "smoke_ok": smoke.get("ok"),
        "smoke_exit_code": smoke.get("exit_code"),
    }
