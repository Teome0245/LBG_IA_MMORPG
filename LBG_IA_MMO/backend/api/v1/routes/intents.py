from fastapi import APIRouter, HTTPException

from models.intents import IntentRequest, IntentResponse
from services.brain_lyra_sync import merge_brain_lyra_if_configured
from services.lyra_regulator import regulate_lyra_if_configured
from services.mmo_lyra_sync import merge_mmo_lyra_if_configured
from services.orchestrator_client import OrchestratorClient, OrchestratorError

router = APIRouter()


@router.post("/route", response_model=IntentResponse)
async def route_intent(payload: IntentRequest) -> IntentResponse:
    await merge_mmo_lyra_if_configured(payload.context)
    await merge_brain_lyra_if_configured(payload.context)
    await regulate_lyra_if_configured(payload.context)
    try:
        client = OrchestratorClient.from_env()
        result = await client.route_intent(payload)
        return result
    except OrchestratorError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

