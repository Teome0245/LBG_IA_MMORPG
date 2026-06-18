import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lbg_companion_bot.api.health import router as health_router
from lbg_companion_bot.api.v1.router import router as v1_router
from lbg_companion_bot.services.autonomy_loop import AutonomyLoop
from lbg_companion_bot.settings import Settings


def create_app() -> FastAPI:
    settings = Settings.from_env()
    application = FastAPI(title=settings.title, version=settings.version)
    loop = AutonomyLoop(settings=settings)

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(health_router)
    application.include_router(v1_router, prefix="/v1")

    # Raccourci de compat (Phase 1)
    @application.get("/")
    def _root() -> dict[str, str]:
        return {"status": "ok", "service": "companion_bot"}

    @application.on_event("startup")
    async def _startup() -> None:
        if settings.autonomous_tick_enabled:
            loop.start()

    @application.on_event("shutdown")
    async def _shutdown() -> None:
        await loop.stop()

    return application


app = create_app()

