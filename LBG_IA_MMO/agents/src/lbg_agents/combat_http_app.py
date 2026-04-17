"""
Agent HTTP pour la capability « combat » : stub structuré (rencontre minimale).

Lancer (venv monorepo) :

    uvicorn lbg_agents.combat_http_app:app --host 0.0.0.0 --port 8040

Orchestrator / dispatch :

    LBG_AGENT_COMBAT_URL="http://127.0.0.1:8040"

Le combat reste **stérile** (meta.sterile) : pas d’effet sur le monde / mmo_server tant
qu’un moteur de combat et une persistance ne sont pas branchés.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lbg_agents.combat_stub import run_combat_stub

app = FastAPI(title="LBG_IA_MMO combat HTTP agent", version="0.2.0")


class InvokeIn(BaseModel):
    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "combat_http",
        "title": app.title,
        "version": app.version,
        "invoke": "POST /invoke",
        "description": "Capability « combat » — stub structuré (encounter), sans effet monde (sterile).",
    }


@app.post("/invoke")
def invoke(p: InvokeIn) -> dict[str, object]:
    return run_combat_stub(actor_id=p.actor_id, text=p.text, context=p.context)  # type: ignore[arg-type]
