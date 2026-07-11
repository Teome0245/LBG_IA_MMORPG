"""Timer core 140 : compile Core3 (Vulcan) + ZB-1 gateway en parallèle."""

from __future__ import annotations

import json
import os
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
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

PARALLEL_SPECS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "dev_game",
        "Plan build Core3 ZB-0/ZB-1 — Vulcan dry-run + poll log VM",
        {
            "core3_build": True,
            "subproject": "core3_build",
            "parallel_prime": True,
            "poll_build_log": True,
        },
    ),
    (
        "dev_game",
        "Audit ZB-1 export JSON live — gateway lbg-ws/2",
        {
            "godot_track": "zb1",
            "subproject": "client_godot",
            "parallel_prime": True,
        },
    ),
)


def job_enabled() -> bool:
    return truthy(os.environ.get("LBG_TEAM_PARALLEL_PRIME_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get(
        "LBG_TEAM_PARALLEL_PRIME_JOB_ACTOR_ID",
        "system:team_parallel_prime",
    ).strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_PARALLEL_PRIME_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_parallel_prime/state.json")


def cooldown_s() -> float:
    try:
        return max(3600.0, float(os.environ.get("LBG_TEAM_PARALLEL_PRIME_JOB_COOLDOWN_S", "28800")))
    except ValueError:
        return 28800.0


def _spawn_one(role: str, objective: str, context: dict[str, Any]) -> dict[str, Any]:
    payload = create_and_run_team_task(
        role=role,
        objective=objective,
        actor_id=spawn_actor_id(),
        context=context,
    )
    summary = task_run_summary(payload)
    return {
        "role": role,
        "objective": objective,
        "context": context,
        **summary,
    }


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {
            "ok": True,
            "outcome": "skipped",
            "reply": "LBG_TEAM_PARALLEL_PRIME_JOB_ENABLED=0",
            "spawned": False,
            "tasks": [],
        }

    st = load_json_state(state_path()) if persist else {}
    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_parallel_prime_job",
        "spawned": False,
        "tasks": [],
    }

    if cooldown_active(st, cooldown_s=cooldown_s()):
        result["outcome"] = "cooldown"
        result["reply"] = f"Cooldown actif ({int(cooldown_s())}s)"
        if persist:
            st["last_check_ts"] = time.time()
            save_json_state(state_path(), st)
        return result

    tasks_out: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with ThreadPoolExecutor(max_workers=len(PARALLEL_SPECS)) as pool:
            futures = {
                pool.submit(_spawn_one, role, objective, dict(ctx)): objective
                for role, objective, ctx in PARALLEL_SPECS
            }
            for fut in as_completed(futures):
                objective = futures[fut]
                try:
                    tasks_out.append(fut.result())
                except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"{objective}: {exc}")

        result["spawned"] = bool(tasks_out)
        result["tasks"] = tasks_out
        result["errors"] = errors
        all_ok = bool(tasks_out) and all(t.get("task_ok") for t in tasks_out) and not errors
        result["ok"] = not errors
        result["outcome"] = "done" if all_ok else ("partial" if tasks_out else "failed")
        result["reply"] = (
            f"Parallèle Vulcan+ZB-1 — {len(tasks_out)} tâche(s), "
            f"ok={sum(1 for t in tasks_out if t.get('task_ok'))}/{len(tasks_out)}"
        )

        if persist:
            save_json_state(
                state_path(),
                {
                    "last_spawn_ts": time.time(),
                    "last_tasks": [
                        {
                            "task_id": t.get("task_id"),
                            "task_ok": t.get("task_ok"),
                            "objective": t.get("objective"),
                        }
                        for t in tasks_out
                    ],
                    "last_outcome": result["outcome"],
                },
            )
    except OSError as exc:
        result["ok"] = False
        result["outcome"] = "error"
        result["error"] = str(exc)
        result["reply"] = f"Échec spawn parallèle : {exc}"

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
