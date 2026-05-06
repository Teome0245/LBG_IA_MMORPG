from typing import Literal

from pydantic import BaseModel, Field


class CapabilityConstraint(BaseModel):
    name: str = Field(..., examples=["dry_run_default"])
    description: str = Field(default="")
    enforceable: bool = True


class CapabilitySpec(BaseModel):
    name: str = Field(..., examples=["npc_dialogue"])
    routed_to: str = Field(..., examples=["agent.dialogue"])
    description: str = Field(default="")
    mode: Literal["local_assistant", "mmo_persona", "system", "mixed"] = "system"
    protocol: Literal["invoke", "execute", "internal"] = "invoke"
    risk_level: Literal["low", "medium", "high"] = "low"
    action_context_key: str | None = Field(default=None, examples=["desktop_action"])
    input_schema: dict[str, object] = Field(default_factory=dict)
    output_schema: dict[str, object] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    constraints: list[CapabilityConstraint] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

