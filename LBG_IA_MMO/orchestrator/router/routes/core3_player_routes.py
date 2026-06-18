"""API joueurs IA Core3 génériques."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["core3-players"])


class Core3PlayerTickRequest(BaseModel):
    via: str | None = Field(default=None, pattern="^(orchestrator|sidecar)$")


@router.post("/core3/players/{player_id}/tick")
def core3_player_tick(player_id: str, payload: Core3PlayerTickRequest) -> dict[str, Any]:
    from lbg_agents.core3_player_autonomy import player_autonomy_tick

    return player_autonomy_tick(player_id, via=payload.via or "sidecar")
