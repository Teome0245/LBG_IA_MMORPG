from fastapi import FastAPI

from router.v1 import router as v1_router
from api.health import router as health_router
from services import brain as svc_brain
from services import lia_autonomy as svc_lia_autonomy
from services import jobs as svc_jobs
from services import proactive as svc_proactive

app = FastAPI(title="LBG_IA_MMO Orchestrator", version="0.1.0")
app.include_router(health_router)
app.include_router(v1_router, prefix="/v1")


@app.on_event("startup")
def _startup() -> None:
    svc_brain.ensure_started()
    svc_lia_autonomy.ensure_started()
    svc_jobs.ensure_started()
    svc_proactive.ensure_started()

