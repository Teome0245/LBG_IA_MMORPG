"""Timer core 140 : round autoconsultation Thémis (24h) — équipe Fable."""

from __future__ import annotations

import json
import os
import time
import urllib.error
from pathlib import Path
from typing import Any

from lbg_agents.team_job_spawn import (
    cooldown_active,
    create_and_run_team_task,
    load_json_state,
    save_json_state,
    task_run_summary,
    truthy,
)


def job_enabled() -> bool:
    return truthy(os.environ.get("LBG_TEAM_AUTOCONSULT_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_AUTOCONSULT_JOB_ACTOR_ID", "system:team_autoconsult").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_AUTOCONSULT_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_autoconsult/state.json")


def cooldown_s() -> float:
    try:
        return max(3600.0, float(os.environ.get("LBG_TEAM_AUTOCONSULT_JOB_COOLDOWN_S", "43200")))
    except ValueError:
        return 43200.0


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {"ok": True, "outcome": "skipped", "spawned": False}

    st = load_json_state(state_path()) if persist else {}
    objective = os.environ.get(
        "LBG_TEAM_AUTOCONSULT_OBJECTIVE",
        "Round autoconsultation équipe — synthèse Thémis + sondes spécialistes",
    ).strip()

    result: dict[str, Any] = {"ok": True, "agent": "spawn_team_autoconsult_job", "spawned": False}

    if cooldown_active(st, cooldown_s=cooldown_s()):
        result["outcome"] = "cooldown"
        if persist:
            st["last_check_ts"] = time.time()
            save_json_state(state_path(), st)
        return result

    try:
        payload = create_and_run_team_task(
            role="pm",
            objective=objective,
            actor_id=spawn_actor_id(),
            context={"autoconsult_round": True, "reunification_brief": True},
        )
        summary = task_run_summary(payload)
        result.update(summary)
        result["spawned"] = True
        result["outcome"] = "done" if summary.get("task_ok") else "ran"
        if persist:
            save_json_state(
                state_path(),
                {"last_spawn_ts": time.time(), "last_task_id": summary.get("task_id"), "last_task_ok": summary.get("task_ok")},
            )
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result["ok"] = False
        result["error"] = str(exc)

    return result


def main() -> int:
    result = run_spawn()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
