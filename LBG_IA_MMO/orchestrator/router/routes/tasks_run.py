"""Route tâches supervisées — proxy jobs synchrone (équivalent P03 /v1/tasks/run)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.supervised import run_supervised_task, supervised_enabled

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskRunIn(BaseModel):
    goal: str = Field(..., min_length=1, max_length=4000)
    actor_id: str = "pilot:supervised"
    context: dict[str, Any] = Field(default_factory=dict)


class TaskRunOut(BaseModel):
    ok: bool
    status: str
    reply: str = ""
    error: str = ""
    state: dict[str, Any] = Field(default_factory=dict)


@router.post("/run", response_model=TaskRunOut)
def tasks_run(req: TaskRunIn) -> TaskRunOut:
    if not supervised_enabled():
        raise HTTPException(
            status_code=503,
            detail="supervised_disabled — définir LBG_SUPERVISED_TASK_ENABLED=1",
        )
    out = run_supervised_task(req.goal, actor_id=req.actor_id, context=req.context)
    return TaskRunOut(
        ok=bool(out.get("ok")),
        status=str(out.get("status") or "unknown"),
        reply=str(out.get("reply") or ""),
        error=str(out.get("error") or ""),
        state=dict(out.get("state") or {}),
    )


@router.get("/status")
def tasks_status() -> dict[str, Any]:
    from services import jobs as svc_jobs

    return {
        "supervised_enabled": supervised_enabled(),
        "jobs_runner": svc_jobs.runner_enabled(),
    }
