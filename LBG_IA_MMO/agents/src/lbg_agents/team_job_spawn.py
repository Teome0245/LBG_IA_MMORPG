"""Helpers partagés — timers core 140 → création + exécution tâches équipe."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def orchestrator_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").strip().rstrip("/")


def api_json(method: str, url: str, body: dict[str, Any] | None = None, *, timeout: float = 300) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def create_and_run_team_task(
    *,
    role: str,
    objective: str,
    actor_id: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = orchestrator_url()
    created = api_json(
        "POST",
        f"{base}/v1/team/tasks",
        {
            "role": role,
            "objective": objective,
            "actor_id": actor_id,
            "priority": "normal",
            "approval_required": False,
            "context": context or {},
        },
    )
    task_id = created.get("id") if isinstance(created, dict) else None
    if not task_id:
        raise ValueError(f"réponse création tâche invalide : {created!r}")
    ran = api_json("POST", f"{base}/v1/team/tasks/{task_id}/run", {})
    return {"task_id": task_id, "created": created, "ran": ran}


def load_json_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def cooldown_active(st: dict[str, Any], key: str = "last_spawn_ts", cooldown_s: float = 86400) -> bool:
    last = float(st.get(key) or 0)
    return bool(last and time.time() - last < cooldown_s)


def task_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    ran = payload.get("ran") if isinstance(payload.get("ran"), dict) else {}
    task_id = payload.get("task_id")
    task_status = ran.get("status")
    task_result = ran.get("result") if isinstance(ran.get("result"), dict) else {}
    task_ok = bool(task_result.get("ok")) if task_status == "done" else False
    return {
        "task_id": task_id,
        "task_status": task_status,
        "task_ok": task_ok if task_status in ("done", "failed") else None,
        "task_result": task_result,
    }
