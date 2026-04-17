"""
Agent HTTP pour la capability « quests » : stub structuré (création + avancement).

Lancer (venv monorepo) :

    uvicorn lbg_agents.quests_http_app:app --host 0.0.0.0 --port 8030

Puis configurer côté orchestrator/dispatch :
    LBG_AGENT_QUESTS_URL="http://127.0.0.1:8030"
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lbg_agents.quests_stub import run_quests_stub

app = FastAPI(title="LBG_IA_MMO quests HTTP agent", version="0.2.0")


class InvokeIn(BaseModel):
    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "quests_http",
        "title": app.title,
        "version": app.version,
        "invoke": "POST /invoke",
        "description": "Capability « quests » — stub structuré (quest + quest_state).",
    }


@app.post("/invoke")
def invoke(p: InvokeIn) -> dict[str, object]:
    # Stub local uniquement (ne lit pas LBG_AGENT_QUESTS_URL — évite la récursion HTTP).
    return run_quests_stub(actor_id=p.actor_id, text=p.text, context=p.context)  # type: ignore[arg-type]

