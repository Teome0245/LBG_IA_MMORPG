"""
Agent HTTP « chef de projet » : stub déterministe ou assistant LLM (plan_de_route).

    uvicorn lbg_agents.pm_http_app:app --host 0.0.0.0 --port 8055

Configurer : LBG_AGENT_PM_URL="http://127.0.0.1:8055"
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lbg_agents.pm_llm import pm_llm_enabled, run_pm_llm_turn, run_pm_llm_turn_stream
from lbg_agents.pm_stub import run_pm_stub

app = FastAPI(title="LBG_IA_MMO PM HTTP agent", version="0.2.0")


class InvokeIn(BaseModel):
    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


def _use_llm(context: dict[str, object]) -> bool:
    if not pm_llm_enabled():
        return False
    if context.get("pm_force_stub") is True:
        return False
    if context.get("pm_use_llm") is True:
        return True
    if context.get("pm_focus") is True:
        return True
    if context.get("pilot_assistant") is True:
        return True
    # Mode chat opérateur : LLM par défaut si configuré
    return context.get("pilot_chat") is True or context.get("prefer_pm_llm") is True


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "pm_http",
        "title": app.title,
        "version": app.version,
        "invoke": "POST /invoke",
        "invoke_stream": "POST /invoke/stream",
        "pm_llm": pm_llm_enabled(),
        "description": "Chef de projet — stub + LLM (plan_de_route).",
    }


@app.post("/invoke")
def invoke(p: InvokeIn) -> dict[str, object]:
    ctx = p.context if isinstance(p.context, dict) else {}
    if _use_llm(ctx):
        return run_pm_llm_turn(actor_id=p.actor_id, text=p.text, context=ctx)  # type: ignore[arg-type]
    return run_pm_stub(actor_id=p.actor_id, text=p.text, context=ctx)  # type: ignore[arg-type]


@app.post("/invoke/stream")
def invoke_stream(p: InvokeIn) -> StreamingResponse:
    """SSE : tool_start, tool_result, token, done."""

    def event_generator():
        ctx = p.context if isinstance(p.context, dict) else {}
        ctx.setdefault("pm_include_repo", True)
        if _use_llm(ctx):
            for evt in run_pm_llm_turn_stream(actor_id=p.actor_id, text=p.text, context=ctx):  # type: ignore[arg-type]
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            return
        out = run_pm_stub(actor_id=p.actor_id, text=p.text, context=ctx)  # type: ignore[arg-type]
        reply = str(out.get("reply") or out.get("brief", {}).get("title") or "")
        yield f"data: {json.dumps({'kind': 'token', 'delta': reply}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'kind': 'done', 'reply': reply, 'brief': out.get('brief'), 'tools': [], 'agent': 'pm_stub'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
