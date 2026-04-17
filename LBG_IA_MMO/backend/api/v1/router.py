from fastapi import APIRouter

from api.v1.routes.intents import router as intents_router
from api.v1.routes.pilot import router as pilot_router

router = APIRouter()
router.include_router(intents_router, prefix="/intents", tags=["intents"])
router.include_router(pilot_router, prefix="/pilot", tags=["pilot"])

