"""Timer core 140 : superviseur Godot autonome (sidecar + lbg-ws/2 readiness)."""

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
    return truthy(os.environ.get("LBG_TEAM_GODOT_SUPERVISOR_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_GODOT_SUPERVISOR_JOB_ACTOR_ID", "system:team_godot_supervisor").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_GODOT_SUPERVISOR_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_godot_supervisor/state.json")


def cooldown_s() -> float:
    try:
        return max(1800.0, float(os.environ.get("LBG_TEAM_GODOT_SUPERVISOR_JOB_COOLDOWN_S", "21600")))
    except ValueError:
        return 21600.0


def default_objective() -> str:
    return os.environ.get(
        "LBG_TEAM_GODOT_SUPERVISOR_JOB_OBJECTIVE",
        "Supervise client Godot — sidecar 246, miroir M1, readiness lbg-ws/2",
    ).strip()


def supervisor_context() -> dict[str, Any]:
    return {"godot_supervisor": True, "godot_mode": "full", "_team_godot_supervisor_spawn": True}


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {
            "ok": True,
            "outcome": "skipped",
            "reply": "LBG_TEAM_GODOT_SUPERVISOR_JOB_ENABLED=0",
            "spawned": False,
            "task_id": None,
        }

    st = load_json_state(state_path()) if persist else {}
    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_godot_supervisor_job",
        "spawned": False,
        "task_id": None,
        "task_status": None,
        "task_ok": None,
    }

    if cooldown_active(st, cooldown_s=cooldown_s()):
        result["outcome"] = "cooldown"
        result["reply"] = f"Cooldown actif ({int(cooldown_s())}s)"
        if persist:
            st["last_check_ts"] = time.time()
            save_json_state(state_path(), st)
        return result

    try:
        payload = create_and_run_team_task(
            role="qa",
            objective=default_objective(),
            actor_id=spawn_actor_id(),
            context=supervisor_context(),
        )
        summary = task_run_summary(payload)
        result.update(summary)
        result["spawned"] = True
        result["outcome"] = "done" if summary.get("task_ok") else ("failed" if summary.get("task_status") == "failed" else "ran")
        result["reply"] = f"Tâche godot_supervisor {summary.get('task_id')} (status={summary.get('task_status')})"

        if persist:
            save_json_state(
                state_path(),
                {
                    "last_spawn_ts": time.time(),
                    "last_task_id": summary.get("task_id"),
                    "last_task_status": summary.get("task_status"),
                    "last_task_ok": summary.get("task_ok"),
                },
            )
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result["ok"] = False
        result["outcome"] = "error"
        result["error"] = str(exc)
        result["reply"] = f"Échec playbook godot supervisor : {exc}"

    return result


def main() -> int:
    result = run_spawn()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        return 3
    if result.get("outcome") == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
