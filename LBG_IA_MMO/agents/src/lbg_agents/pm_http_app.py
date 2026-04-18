"""
Agent HTTP « chef de projet » : même contrat POST /invoke que les autres agents.

    uvicorn lbg_agents.pm_http_app:app --host 0.0.0.0 --port 8055

Configurer : LBG_AGENT_PM_URL="http://127.0.0.1:8055"
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lbg_agents.pm_stub import run_pm_stub

app = FastAPI(title="LBG_IA_MMO PM HTTP agent", version="0.1.0")


class InvokeIn(BaseModel):
    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "pm_http",
        "title": app.title,
        "version": app.version,
        "invoke": "POST /invoke",
        "description": "Agent chef de projet — brief structuré (stub, sans LLM).",
    }


@app.post("/invoke")
def invoke(p: InvokeIn) -> dict[str, object]:
    return run_pm_stub(actor_id=p.actor_id, text=p.text, context=p.context)  # type: ignore[arg-type]
