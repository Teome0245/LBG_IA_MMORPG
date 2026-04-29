from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import brain as svc_brain


router = APIRouter(tags=["brain"])


class BrainStatus(BaseModel):
    enabled: bool
    interval_s: int = Field(..., ge=5, le=3600)
    gauges: dict[str, float] = Field(default_factory=dict)
    intent: str = "monitor"
    narrative: str = ""
    approval_requests: list[dict[str, object]] = Field(default_factory=list)
    last_persist_error: str | None = None
    last_persist_ts: float | None = None
    last_restart_ts: float | None = None
    last_tick_ts: float | None = None
    last_tick_ok: bool | None = None
    last_error: str | None = None
    last_actions: list[dict[str, object]] | None = None
    last_selfcheck: dict[str, object] | None = None
    last_desktop_healthz: dict[str, object] | None = None


class BrainToggleRequest(BaseModel):
    enabled: bool


class BrainApproveRequest(BaseModel):
    request_id: str = Field(..., min_length=1)


@router.get("/brain/status", response_model=BrainStatus)
def brain_status() -> BrainStatus:
    st = svc_brain.get_state()
    return BrainStatus(**st.__dict__)


@router.post("/brain/toggle", response_model=BrainStatus)
def brain_toggle(payload: BrainToggleRequest) -> BrainStatus:
    st = svc_brain.set_enabled(payload.enabled)
    return BrainStatus(**st.__dict__)


@router.post("/brain/approve", response_model=BrainStatus)
def brain_approve(payload: BrainApproveRequest) -> BrainStatus:
    st = svc_brain.approve_request(payload.request_id)
    return BrainStatus(**st.__dict__)

