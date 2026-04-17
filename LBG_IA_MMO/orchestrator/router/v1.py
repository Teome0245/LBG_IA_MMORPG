from fastapi import APIRouter

from router.routes.capabilities import router as capabilities_router
from router.routes.route_intent import router as route_intent_router

router = APIRouter()
router.include_router(capabilities_router)
router.include_router(route_intent_router)

