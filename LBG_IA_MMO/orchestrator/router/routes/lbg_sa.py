"""API LBG Studios Agents (LBG_SA) — meta modules + kickoff Team."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lbg_sa.memory_store import lbg_sa_memory_enabled, memory_root, team_db_path
from lbg_sa.module_registry import modules_as_dicts
from lbg_sa.team_submit import enqueue_lbg_sa_kickoff_tasks

router = APIRouter(tags=["lbg_sa"])


class LbgSaMetaResponse(BaseModel):
    version: str = "phase0"
    product: str = "LBG Studios Agents"
    alias: str = "LBG_SA"
    memory_enabled: bool
    memory_root: str
    team_db_path: str
    modules: list[dict[str, object]] = Field(default_factory=list)


class LbgSaKickoffRequest(BaseModel):
    actor_id: str = "pilot:lbg_sa"
    force: bool = False


class LbgSaKickoffResponse(BaseModel):
    ok: bool
    skipped: str | None = None
    batch: str | None = None
    tasks: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None


@router.get("/lbg_sa/meta", response_model=LbgSaMetaResponse)
def lbg_sa_meta() -> LbgSaMetaResponse:
    return LbgSaMetaResponse(
        memory_enabled=lbg_sa_memory_enabled(),
        memory_root=str(memory_root()),
        team_db_path=team_db_path(),
        modules=modules_as_dicts(),
    )


@router.post("/lbg_sa/team/kickoff", response_model=LbgSaKickoffResponse)
def lbg_sa_team_kickoff(payload: LbgSaKickoffRequest) -> LbgSaKickoffResponse:
    out = enqueue_lbg_sa_kickoff_tasks(actor_id=payload.actor_id, force=payload.force)
    if not out.get("ok"):
        raise HTTPException(status_code=503, detail=str(out.get("error") or "team_disabled"))
    return LbgSaKickoffResponse(
        ok=True,
        skipped=str(out["skipped"]) if out.get("skipped") else None,
        batch=str(out.get("batch") or ""),
        tasks=list(out.get("tasks") or []),
    )
