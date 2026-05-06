from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.action_proposal import ActionProposal, propose_action_from_text

router = APIRouter()


class ActionProposalRequest(BaseModel):
    actor_id: str
    text: str = Field(..., min_length=1)
    context: dict[str, object] = Field(default_factory=dict)


class ActionProposalResponse(BaseModel):
    actor_id: str
    proposal: ActionProposal | None = None
    reason: str | None = None


@router.post("/action-proposal", response_model=ActionProposalResponse, tags=["assistant"])
def propose_action(payload: ActionProposalRequest) -> ActionProposalResponse:
    result = propose_action_from_text(payload.text, payload.context)
    return ActionProposalResponse(actor_id=payload.actor_id, proposal=result.proposal, reason=result.reason)
