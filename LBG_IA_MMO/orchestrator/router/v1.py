from fastapi import APIRouter

from router.routes.tasks_run import router as tasks_run_router
from router.routes.action_proposal import router as action_proposal_router
from router.routes.capabilities import router as capabilities_router
from router.routes.brain import router as brain_router
from router.routes.jobs import router as jobs_router
from router.routes.proactive import router as proactive_router
from router.routes.route_intent import router as route_intent_router
from router.routes.infra_alerts import router as infra_alerts_router
from router.routes.lia_incarnation import router as lia_incarnation_router
from router.routes.core3_player_routes import router as core3_players_router

router = APIRouter()
router.include_router(tasks_run_router)
router.include_router(action_proposal_router)
router.include_router(capabilities_router)
router.include_router(brain_router)
router.include_router(jobs_router)
router.include_router(infra_alerts_router)
router.include_router(proactive_router)
router.include_router(route_intent_router)
router.include_router(lia_incarnation_router)
router.include_router(core3_players_router)

