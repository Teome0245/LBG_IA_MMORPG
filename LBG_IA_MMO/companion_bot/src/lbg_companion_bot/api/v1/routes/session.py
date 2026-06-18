from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lbg_companion_bot.services import db as svc_db
from lbg_companion_bot.services.chat_service import autonomous_tick
from lbg_companion_bot.settings import Settings

router = APIRouter()


class SessionMessage(BaseModel):
    id: int | None = None
    role: str
    content: str
    ts: float


class SessionResponse(BaseModel):
    session_id: str
    last_message_id: int = 0
    messages: list[SessionMessage] = Field(default_factory=list)
    engine_state: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class TickResponse(BaseModel):
    session_id: str
    last_message_id: int = 0
    nudge: str | None = None
    debug: dict[str, Any] | None = None


class EventsResponse(BaseModel):
    session_id: str
    after_id: int
    last_message_id: int
    events: list[SessionMessage] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, limit: int = Query(default=30, ge=1, le=200), debug: bool | None = Query(default=None)) -> SessionResponse:
    settings = Settings.from_env()
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "hint": "session_id vide"})
    # Comportement Phase 1.5 : idempotent. Si la session n'existe pas encore, on la crée et on retourne vide.
    con = svc_db.connect(settings.db_path)
    try:
        svc_db.ensure_session(con, sid)

        msgs = svc_db.get_history(con, session_id=sid, limit=int(limit))
        last_id = svc_db.get_last_message_id(con, session_id=sid)
        state = svc_db.load_engine_state(con, session_id=sid)
        meta = svc_db.get_session_meta(con, session_id=sid)

        dbg = settings.debug_default if debug is None else bool(debug)
        return SessionResponse(
            session_id=sid,
            last_message_id=last_id,
            messages=[SessionMessage(id=m.id, role=m.role, content=m.content, ts=m.ts) for m in msgs],
            engine_state=state if dbg else None,
            meta=meta.__dict__ if dbg else None,
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


@router.post("/session/{session_id}/tick", response_model=TickResponse)
async def tick_session(session_id: str, debug: bool | None = Query(default=None)) -> TickResponse:
    settings = Settings.from_env()
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "hint": "session_id vide"})

    dbg = settings.debug_default if debug is None else bool(debug)
    con = svc_db.connect(settings.db_path)
    try:
        nudge, dbg_obj = autonomous_tick(con=con, settings=settings, session_id=sid, debug=dbg)
        last_id = svc_db.get_last_message_id(con, session_id=sid)
        return TickResponse(session_id=sid, last_message_id=last_id, nudge=nudge, debug=dbg_obj if dbg else None)
    finally:
        try:
            con.close()
        except Exception:
            pass


@router.get("/session/{session_id}/events", response_model=EventsResponse)
def get_events(
    session_id: str,
    after_id: int = Query(default=0, ge=0, le=2_000_000_000),
    limit: int = Query(default=50, ge=1, le=500),
    debug: bool | None = Query(default=None),
) -> EventsResponse:
    """
    Poll incrémental : retourne les messages > after_id.
    Le JSON debug n'est renvoyé que si debug=true (ou debug_default).
    """
    settings = Settings.from_env()
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "hint": "session_id vide"})
    con = svc_db.connect(settings.db_path)
    try:
        svc_db.ensure_session(con, sid)

        events = svc_db.get_messages_after_id(con, session_id=sid, after_id=int(after_id), limit=int(limit))
        last_id = svc_db.get_last_message_id(con, session_id=sid)

        dbg = settings.debug_default if debug is None else bool(debug)
        dbg_obj: dict[str, Any] | None = None
        if dbg:
            meta = svc_db.get_session_meta(con, session_id=sid)
            dbg_obj = {
                "meta": meta.__dict__,
                "engine_state": svc_db.load_engine_state(con, session_id=sid),
            }
        return EventsResponse(
            session_id=sid,
            after_id=int(after_id),
            last_message_id=last_id,
            events=[SessionMessage(id=m.id, role=m.role, content=m.content, ts=m.ts) for m in events],
            debug=dbg_obj if dbg else None,
        )
    finally:
        try:
            con.close()
        except Exception:
            pass

