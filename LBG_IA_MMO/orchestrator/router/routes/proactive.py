"""API statut couche proactive."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import proactive as svc_proactive

router = APIRouter(tags=["proactive"])


class ProactiveStatus(BaseModel):
    enabled: bool = False
    auto_jobs: bool = False
    interval_s: float = 300.0
    ticks: int = 0
    mode: str = "proactif_leger"
    tension: float = 0.0
    curiosite: float = 0.0
    silence_seconds_est: float = 0.0
    auto_jobs_spawned: int = 0
    last_job_id: str | None = None
    last_action: dict[str, object] | None = None
    infra_signals: dict[str, object] = Field(default_factory=dict)


@router.get("/proactive/status", response_model=ProactiveStatus)
def proactive_status() -> ProactiveStatus:
    data = svc_proactive.get_status()
    return ProactiveStatus(**{k: data[k] for k in ProactiveStatus.model_fields if k in data})
