from fastapi import APIRouter

from lbg_companion_bot.api.v1.routes.chat import router as chat_router
from lbg_companion_bot.api.v1.routes.session import router as session_router

router = APIRouter()
router.include_router(chat_router, tags=["chat"])
router.include_router(session_router, tags=["session"])

