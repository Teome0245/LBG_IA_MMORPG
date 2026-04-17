from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    actor_id: str = Field(..., examples=["player:123"])
    text: str = Field(..., min_length=1, examples=["Je veux parler au forgeron."])
    context: dict[str, object] = Field(default_factory=dict)


class IntentResponse(BaseModel):
    intent: str = Field(..., examples=["npc_dialogue"])
    confidence: float = Field(..., ge=0.0, le=1.0, examples=[0.9])
    routed_to: str = Field(..., examples=["agent.dialogue"])
    output: dict[str, object] = Field(default_factory=dict)

