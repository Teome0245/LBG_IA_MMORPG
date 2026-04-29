from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class Capability(BaseModel):
    name: str
    description: Optional[str] = None

class CapabilitiesResponse(BaseModel):
    agent_id: str
    capabilities: List[Capability]

class ActionRequest(BaseModel):
    action: str
    parameters: Dict[str, Any] = {}

class InstallRequest(BaseModel):
    action: str
    code: str
    description: Optional[str] = None

class ActionResult(BaseModel):
    status: str  # "success" | "error"
    return_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error_message: Optional[str] = None

