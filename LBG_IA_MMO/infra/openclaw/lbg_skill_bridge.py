#!/usr/bin/env python3
"""Bridge HTTP LBG ↔ skills ops — contrat /v1/skills/{id}/run pour l'orchestrateur."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# PYTHONPATH orchestrator + agents/src (systemd)
_ROOT = Path(__file__).resolve().parents[2]
for p in (_ROOT / "orchestrator", _ROOT / "agents" / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI
from pydantic import BaseModel, Field

from team.openclaw_adapter import list_skills, openclaw_base_url, openclaw_enabled, run_skill

app = FastAPI(title="LBG OpenClaw Skill Bridge", version="0.1.0")


class SkillRunRequest(BaseModel):
    env: dict[str, str] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "service": "lbg-openclaw-bridge",
        "openclaw_enabled": openclaw_enabled(),
        "openclaw_native_url": openclaw_base_url() or None,
    }


@app.get("/v1/skills")
def get_skills() -> dict[str, object]:
    return {"skills": list_skills()}


@app.post("/v1/skills/{skill_id}/run")
def post_run_skill(skill_id: str, body: SkillRunRequest | None = None) -> dict[str, object]:
    payload = body or SkillRunRequest()
    return run_skill(skill_id, env=payload.env, prefer_openclaw=False)


def main() -> None:
    import uvicorn

    host = os.environ.get("LBG_OPENCLAW_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("LBG_OPENCLAW_BRIDGE_PORT", "18790"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
