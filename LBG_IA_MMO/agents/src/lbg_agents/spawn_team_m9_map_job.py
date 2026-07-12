"""Timer core 140 : rotation M9a planète / M9b minimap / M9c carte M / M9 complet."""

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

TRACKS = ("m9a", "m9b", "m9c", "m9_full")

TRACK_OBJECTIVES = {
    "m9a": "Audit M9a Scrapaltai — texture planète + POI sync + pipeline export Godot",
    "m9b": "Audit M9b minimap HUD — SubViewport coin écran style SWG",
    "m9c": "Audit M9c carte planétaire M — waypoints + locations tree",
    "m9_full": "Audit M9 complet — Scrapaltai 2D + minimap + carte M Prime Client",
}


def job_enabled() -> bool:
    return truthy(os.environ.get("LBG_TEAM_M9_MAP_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_M9_MAP_JOB_ACTOR_ID", "system:team_m9_map").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_M9_MAP_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_m9_map/state.json")


def cooldown_s() -> float:
    try:
        return max(3600.0, float(os.environ.get("LBG_TEAM_M9_MAP_JOB_COOLDOWN_S", "43200")))
    except ValueError:
        return 43200.0


def next_track(state: dict[str, Any]) -> str:
    override = os.environ.get("LBG_TEAM_M9_MAP_JOB_TRACK", "").strip().lower()
    if override in TRACKS:
        return override
    last = str(state.get("last_track") or "")
    try:
        idx = TRACKS.index(last) if last in TRACKS else -1
    except ValueError:
        idx = -1
    return TRACKS[(idx + 1) % len(TRACKS)]


def track_context(track: str) -> dict[str, Any]:
    return {
        "m9_track": track,
        "subproject": "prime_client_2d",
        "dev_game_focus": True,
        "_team_m9_map_spawn": True,
    }


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {
            "ok": True,
            "outcome": "skipped",
            "reply": "LBG_TEAM_M9_MAP_JOB_ENABLED=0",
            "spawned": False,
            "task_id": None,
        }

    st = load_json_state(state_path()) if persist else {}
    track = next_track(st)
    objective = os.environ.get(
        f"LBG_TEAM_M9_MAP_{track.upper()}_OBJECTIVE",
        TRACK_OBJECTIVES[track],
    ).strip()

    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_m9_map_job",
        "track": track,
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
            role="dev_game",
            objective=objective,
            actor_id=spawn_actor_id(),
            context=track_context(track),
        )
        summary = task_run_summary(payload)
        result.update(summary)
        result["spawned"] = True
        result["outcome"] = "done" if summary.get("task_ok") else (
            "failed" if summary.get("task_status") == "failed" else "ran"
        )
        result["reply"] = f"Tâche M9 {track} {summary.get('task_id')} (status={summary.get('task_status')})"

        if persist:
            save_json_state(
                state_path(),
                {
                    "last_spawn_ts": time.time(),
                    "last_track": track,
                    "last_task_id": summary.get("task_id"),
                    "last_task_status": summary.get("task_status"),
                    "last_task_ok": summary.get("task_ok"),
                },
            )
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result["ok"] = False
        result["outcome"] = "error"
        result["error"] = str(exc)
        result["reply"] = f"Échec playbook M9 map : {exc}"

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
