from fastapi import APIRouter
from pydantic import BaseModel

from capabilities.spec import CapabilitySpec
from shared_registry import capability_registry

router = APIRouter()


class CapabilitiesResponse(BaseModel):
    capabilities: list[CapabilitySpec]


@router.get("/capabilities", response_model=CapabilitiesResponse, tags=["introspection"])
def list_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(capabilities=capability_registry.list())
