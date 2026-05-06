from fastapi import APIRouter

from router.routes.action_proposal import router as action_proposal_router
from router.routes.capabilities import router as capabilities_router
from router.routes.brain import router as brain_router
from router.routes.route_intent import router as route_intent_router

router = APIRouter()
router.include_router(action_proposal_router)
router.include_router(capabilities_router)
router.include_router(brain_router)
router.include_router(route_intent_router)

