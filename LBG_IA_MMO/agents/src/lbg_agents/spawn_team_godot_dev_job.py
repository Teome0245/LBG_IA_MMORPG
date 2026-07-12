"""Timer core 140 : rotation dev Godot IA — Iris (2D/M9) / Hermès (SOE/gateway)."""

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

TRACKS = ("iris_m9", "iris_m9c", "hermes_soe", "hermes_live", "godot_full")

TRACK_OBJECTIVES = {
    "iris_m9": "Iris — audit M9 Scrapaltai planète + minimap (Prime Client 2D)",
    "iris_m9c": "Iris — audit M9c carte planétaire M + waypoints",
    "hermes_soe": "Hermès — audit SOE M3/M5 + gateway Prime",
    "hermes_live": "Hermès — audit client live SOE + ZB-1 + lbg-ws/2",
    "godot_full": "Iris + Hermès — audit Godot complet Prime Client",
}

TRACK_CONTEXT = {
    "iris_m9": {"godot_dev_persona": "iris", "godot_dev_track": "m9_full", "subproject": "godot_iris"},
    "iris_m9c": {"godot_dev_persona": "iris", "godot_dev_track": "m9c", "subproject": "godot_iris"},
    "hermes_soe": {"godot_dev_persona": "hermes", "godot_dev_track": "soe_m3", "subproject": "godot_hermes"},
    "hermes_live": {"godot_dev_persona": "hermes", "godot_dev_track": "client_live", "subproject": "godot_hermes"},
    "godot_full": {"godot_dev_persona": "iris", "godot_dev_track": "iris_full", "subproject": "godot_iris"},
}


def job_enabled() -> bool:
    return truthy(os.environ.get("LBG_TEAM_GODOT_DEV_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_GODOT_DEV_JOB_ACTOR_ID", "system:team_godot_dev").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_GODOT_DEV_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_godot_dev/state.json")


def cooldown_s() -> float:
    try:
        return max(3600.0, float(os.environ.get("LBG_TEAM_GODOT_DEV_JOB_COOLDOWN_S", "28800")))
    except ValueError:
        return 28800.0


def next_track(state: dict[str, Any]) -> str:
    override = os.environ.get("LBG_TEAM_GODOT_DEV_JOB_TRACK", "").strip().lower()
    if override in TRACKS:
        return override
    last = str(state.get("last_track") or "")
    idx = TRACKS.index(last) if last in TRACKS else -1
    return TRACKS[(idx + 1) % len(TRACKS)]


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {"ok": True, "outcome": "skipped", "spawned": False, "task_id": None}

    st = load_json_state(state_path()) if persist else {}
    track = next_track(st)
    objective = os.environ.get(
        f"LBG_TEAM_GODOT_DEV_{track.upper()}_OBJECTIVE",
        TRACK_OBJECTIVES[track],
    ).strip()
    ctx = dict(TRACK_CONTEXT[track])
    ctx["_team_godot_dev_spawn"] = True
    ctx["dev_godot_focus"] = True

    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_godot_dev_job",
        "track": track,
        "spawned": False,
        "task_id": None,
    }

    if cooldown_active(st, cooldown_s=cooldown_s()):
        result["outcome"] = "cooldown"
        if persist:
            st["last_check_ts"] = time.time()
            save_json_state(state_path(), st)
        return result

    try:
        payload = create_and_run_team_task(
            role="dev_godot",
            objective=objective,
            actor_id=spawn_actor_id(),
            context=ctx,
        )
        summary = task_run_summary(payload)
        result.update(summary)
        result["spawned"] = True
        result["outcome"] = "done" if summary.get("task_ok") else "ran"
        if persist:
            save_json_state(
                state_path(),
                {
                    "last_spawn_ts": time.time(),
                    "last_track": track,
                    "last_task_id": summary.get("task_id"),
                    "last_task_ok": summary.get("task_ok"),
                },
            )
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result["ok"] = False
        result["outcome"] = "error"
        result["error"] = str(exc)

    return result


def main() -> int:
    result = run_spawn()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
