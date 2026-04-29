from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lbg_agents.desktop_executor import run_desktop_action

app = FastAPI(title="lbg-agent-desktop", version="0.1.0")


class InvokeRequest(BaseModel):
    actor_id: str
    text: str = Field(default="")
    context: dict[str, object] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"status": "ok", "service": "desktop_http", "version": "0.1.0"}


@app.post("/invoke")
def invoke(payload: InvokeRequest) -> dict[str, object]:
    ctx = payload.context if isinstance(payload.context, dict) else {}
    raw = ctx.get("desktop_action")
    if not isinstance(raw, dict):
        return {
            "agent": "desktop_executor",
            "handler": "desktop",
            "actor_id": payload.actor_id,
            "request_text": payload.text,
            "ok": False,
            "outcome": "bad_request",
            "error": "Aucune desktop_action dans context.",
            "hint": 'Ex. {"desktop_action": {"kind":"open_url","url":"https://example.org"}}',
        }
    return run_desktop_action(actor_id=payload.actor_id, text=payload.text, action=raw, context=ctx)  # type: ignore[arg-type]

