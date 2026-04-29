from fastapi import FastAPI

from router.v1 import router as v1_router
from api.health import router as health_router
from services import brain as svc_brain

app = FastAPI(title="LBG_IA_MMO Orchestrator", version="0.1.0")
app.include_router(health_router)
app.include_router(v1_router, prefix="/v1")


@app.on_event("startup")
def _startup() -> None:
    svc_brain.ensure_started()

