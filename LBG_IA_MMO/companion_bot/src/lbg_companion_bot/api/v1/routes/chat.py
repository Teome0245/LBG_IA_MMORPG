from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lbg_companion_bot.services import db as svc_db
from lbg_companion_bot.services.chat_service import chat_turn
from lbg_companion_bot.settings import Settings

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    text: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    debug: dict[str, Any] | None = None


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, debug: bool | None = Query(default=None)) -> ChatResponse:
    settings = Settings.from_env()
    dbg = settings.debug_default if debug is None else bool(debug)

    session_id = (payload.session_id or "").strip() or os.environ.get("LBG_COMPANION_DEFAULT_SESSION", "").strip() or f"sess-{uuid.uuid4().hex[:12]}"
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "hint": "text vide"})

    con = svc_db.connect(settings.db_path)
    try:
        reply, dbg_obj = chat_turn(con=con, settings=settings, session_id=session_id, user_text=text, debug=dbg)
        return ChatResponse(reply=reply, session_id=session_id, debug=dbg_obj if dbg else None)
    finally:
        try:
            con.close()
        except Exception:
            pass

