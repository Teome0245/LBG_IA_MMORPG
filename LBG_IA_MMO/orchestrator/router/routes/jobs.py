"""
API du moteur de jobs autonome ("type Cowork", sous garde-fous).

- ``POST /v1/jobs`` : créer un job depuis un objectif en langage naturel (planifié
  immédiatement, exécuté en tâche de fond par le runner si activé).
- ``GET  /v1/jobs`` : lister les jobs (optionnellement filtrés par ``actor_id``).
- ``GET  /v1/jobs/{id}`` : état complet d'un job (étapes, policy, résultats, timeline).
- ``POST /v1/jobs/{id}/approve`` : autoriser (token) un job en ``waiting_approval``.
- ``POST /v1/jobs/{id}/cancel`` : annuler un job.
- ``POST /v1/jobs/{id}/advance`` : faire avancer manuellement d'une étape (pilotage / debug).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import jobs as svc_jobs

router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    context: dict[str, object] = Field(default_factory=dict)
    approval_token: str | None = None
    auto_start: bool = True


class ApproveJobRequest(BaseModel):
    token: str = Field(..., min_length=1)


class JobView(BaseModel):
    id: str
    actor_id: str
    objective: str
    status: str
    plan_source: str | None = None
    pre_authorized: bool = False
    cursor: int = 0
    steps: list[dict[str, object]] = Field(default_factory=list)
    events: list[dict[str, object]] = Field(default_factory=list)
    result_summary: str | None = None
    trace_id: str = ""
    created_ts: float = 0.0
    updated_ts: float = 0.0


class JobSummary(BaseModel):
    id: str
    actor_id: str
    objective: str
    status: str
    plan_source: str | None = None
    n_steps: int = 0
    result_summary: str | None = None
    created_ts: float = 0.0
    updated_ts: float = 0.0


class JobListResponse(BaseModel):
    jobs: list[JobSummary] = Field(default_factory=list)


def _to_view(job: svc_jobs.Job) -> JobView:
    data = asdict(job)
    data.pop("stored_approval_token", None)
    data["steps"] = [asdict(s) if not isinstance(s, dict) else s for s in job.steps]
    return JobView(**{k: data[k] for k in JobView.model_fields if k in data})


def _to_summary(job: svc_jobs.Job) -> JobSummary:
    return JobSummary(
        id=job.id,
        actor_id=job.actor_id,
        objective=job.objective,
        status=job.status,
        plan_source=job.plan_source,
        n_steps=len(job.steps),
        result_summary=job.result_summary,
        created_ts=job.created_ts,
        updated_ts=job.updated_ts,
    )


@router.post("/jobs", response_model=JobView)
def create_job(payload: CreateJobRequest) -> JobView:
    job = svc_jobs.create_job(
        actor_id=payload.actor_id,
        objective=payload.objective,
        context=payload.context,
        approval_token=payload.approval_token,
        auto_start=payload.auto_start,
    )
    return _to_view(job)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(actor_id: str | None = None) -> JobListResponse:
    jobs = svc_jobs.list_jobs(actor_id=actor_id)
    return JobListResponse(jobs=[_to_summary(j) for j in jobs])


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str) -> JobView:
    job = svc_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job introuvable")
    return _to_view(job)


@router.post("/jobs/{job_id}/approve", response_model=JobView)
def approve_job(job_id: str, payload: ApproveJobRequest) -> JobView:
    job = svc_jobs.approve_job(job_id, payload.token)
    if job is None:
        raise HTTPException(status_code=404, detail="job introuvable")
    return _to_view(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str) -> JobView:
    job = svc_jobs.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job introuvable")
    return _to_view(job)


@router.post("/jobs/{job_id}/advance", response_model=JobView)
def advance_job(job_id: str) -> JobView:
    job = svc_jobs.advance_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job introuvable")
    return _to_view(job)
