"""API incarnation Lia (orchestrateur → Core3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["lia"])


class LiaHearRequest(BaseModel):
    from_player: str = Field(default="Gally", min_length=1)
    text: str = Field(..., min_length=1)


class LiaTickRequest(BaseModel):
    prompt: str | None = None


class LiaConnectRequest(BaseModel):
    wait: bool = True
    wait_s: int | None = Field(default=None, ge=15, le=600)
    force_restart: bool = False


@router.post("/lia/connect")
def lia_connect(payload: LiaConnectRequest) -> dict[str, Any]:
    from lbg_agents.lia_connection import connect_lia

    return connect_lia(
        wait=payload.wait,
        wait_s=payload.wait_s,
        force_restart=payload.force_restart,
    )


@router.post("/lia/hear")
def lia_hear(payload: LiaHearRequest) -> dict[str, Any]:
    from lbg_agents.lia_orchestrator import hear_player_message

    return hear_player_message(from_player=payload.from_player, text=payload.text)


@router.post("/lia/tick")
def lia_tick(payload: LiaTickRequest) -> dict[str, Any]:
    from lbg_agents.lia_orchestrator import autonomy_tick, incarnate_player_think

    if payload.prompt and payload.prompt.strip():
        return incarnate_player_think(prompt=payload.prompt.strip())
    return autonomy_tick()
