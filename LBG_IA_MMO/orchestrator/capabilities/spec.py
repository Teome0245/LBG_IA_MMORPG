from pydantic import BaseModel, Field


class CapabilitySpec(BaseModel):
    name: str = Field(..., examples=["npc_dialogue"])
    routed_to: str = Field(..., examples=["agent.dialogue"])
    description: str = Field(default="")

