"""
Mode supervisé — boucle plan → exécution via le moteur de jobs (équivalent pragmatique P03 LangGraph).
"""

from __future__ import annotations

import os
from typing import Any

from services import jobs as svc_jobs

_TERMINAL = frozenset({"done", "failed", "cancelled", "waiting_approval"})


def supervised_enabled() -> bool:
    return os.environ.get("LBG_SUPERVISED_TASK_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _max_steps() -> int:
    try:
        return max(1, min(64, int(os.environ.get("LBG_SUPERVISED_MAX_STEPS", "32").strip())))
    except ValueError:
        return 32


def _build_reply(job: svc_jobs.Job) -> str:
    if job.result_summary:
        base = job.result_summary.strip()
    else:
        done = sum(1 for s in job.steps if s.status == "done")
        base = f"Job {job.id[:8]}… — {done}/{len(job.steps)} étape(s) — statut {job.status}"

    lines = [base]
    if job.plan_source:
        lines.append(f"Plan : {job.plan_source}")
    if job.status == "waiting_approval":
        lines.append("Approbation requise — validez dans Pilot ▸ Jobs ou fournissez un token.")
    elif job.status == "done":
        for s in job.steps:
            if s.status == "done" and (s.summary or s.capability):
                lines.append(f"✓ {s.summary or s.capability}")
    elif job.status == "failed":
        for s in job.steps:
            if s.status == "failed" and s.error:
                lines.append(f"✗ {s.summary or s.capability}: {s.error[:200]}")
    return "\n\n".join(lines)


def run_supervised_task(
    goal: str,
    *,
    actor_id: str = "pilot:supervised",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exécute un objectif supervisé de bout en bout (bloquant)."""
    if not supervised_enabled():
        return {
            "ok": False,
            "status": "disabled",
            "reply": "",
            "error": "supervised_disabled — LBG_SUPERVISED_TASK_ENABLED=0",
            "state": {},
        }

    ctx = dict(context) if isinstance(context, dict) else {}
    ctx.setdefault("_job_synthesis", True)
    approval = ctx.get("devops_approval") or ctx.get("desktop_approval") or ctx.get("approval_token")
    approval_s = approval.strip() if isinstance(approval, str) else None

    job = svc_jobs.create_job(
        actor_id=actor_id,
        objective=goal.strip(),
        context=ctx,
        approval_token=approval_s,
        auto_start=True,
    )
    final = svc_jobs.run_job_to_completion(job.id, max_steps=_max_steps()) or job
    ok = final.status == "done"
    err = ""
    if final.status == "failed":
        err = final.result_summary or "échec supervisé"
    elif final.status == "waiting_approval":
        err = "waiting_approval"

    retries = len(final.error_log) if final.error_log else 0
    state: dict[str, Any] = {
        "job_id": final.id,
        "plan_source": final.plan_source,
        "retries": retries,
        "n_steps": len(final.steps),
        "steps": [
            {
                "capability": s.capability,
                "summary": s.summary,
                "status": s.status,
            }
            for s in final.steps
        ],
    }

    return {
        "ok": ok,
        "status": final.status,
        "reply": _build_reply(final),
        "error": err,
        "state": state,
    }
