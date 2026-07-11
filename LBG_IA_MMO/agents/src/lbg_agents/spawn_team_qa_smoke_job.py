"""Timer core 140 : playbook L1 smoke quotidien → tâche équipe ``qa`` (smoke_vm_lan.sh)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def job_enabled() -> bool:
    return _truthy(os.environ.get("LBG_TEAM_QA_SMOKE_JOB_ENABLED", "1"))


def orchestrator_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").strip().rstrip("/")


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_QA_SMOKE_JOB_ACTOR_ID", "system:team_qa_smoke").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_QA_SMOKE_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_qa_smoke/state.json")


def cooldown_s() -> float:
    try:
        return max(3600.0, float(os.environ.get("LBG_TEAM_QA_SMOKE_JOB_COOLDOWN_S", "86400")))
    except ValueError:
        return 86400.0


def default_objective() -> str:
    return os.environ.get(
        "LBG_TEAM_QA_SMOKE_JOB_OBJECTIVE",
        "Smoke LAN read-only quotidien — healthz orchestrateur/backend + systemd via smoke_vm_lan.sh",
    ).strip()


def _load_state() -> dict[str, Any]:
    path = state_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(payload: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _should_spawn(st: dict[str, Any]) -> bool:
    last = float(st.get("last_spawn_ts") or 0)
    if last and time.time() - last < cooldown_s():
        return False
    return True


def _api_json(method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _create_and_run_qa_task(objective: str) -> dict[str, Any]:
    base = orchestrator_url()
    created = _api_json(
        "POST",
        f"{base}/v1/team/tasks",
        {
            "role": "qa",
            "objective": objective,
            "actor_id": spawn_actor_id(),
            "priority": "normal",
            "approval_required": False,
            "context": {"_team_qa_smoke_spawn": True},
        },
    )
    task_id = created.get("id") if isinstance(created, dict) else None
    if not task_id:
        raise ValueError(f"réponse création tâche invalide : {created!r}")

    ran = _api_json("POST", f"{base}/v1/team/tasks/{task_id}/run", {})
    return {"task_id": task_id, "created": created, "ran": ran}


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {
            "ok": True,
            "outcome": "skipped",
            "reply": "LBG_TEAM_QA_SMOKE_JOB_ENABLED=0",
            "spawned": False,
            "task_id": None,
        }

    st = _load_state() if persist else {}
    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_qa_smoke_job",
        "spawned": False,
        "task_id": None,
        "task_status": None,
        "task_ok": None,
    }

    if not _should_spawn(st):
        result["outcome"] = "cooldown"
        result["reply"] = f"Cooldown actif ({int(cooldown_s())}s) — pas de nouvelle tâche qa"
        if persist:
            st["last_check_ts"] = time.time()
            _save_state(st)
        return result

    try:
        payload = _create_and_run_qa_task(default_objective())
        ran = payload.get("ran") if isinstance(payload.get("ran"), dict) else {}
        task_id = payload.get("task_id")
        task_status = ran.get("status")
        task_result = ran.get("result") if isinstance(ran.get("result"), dict) else {}
        task_ok = bool(task_result.get("ok")) if task_status == "done" else False

        result["spawned"] = True
        result["task_id"] = task_id
        result["task_status"] = task_status
        result["task_ok"] = task_ok if task_status in ("done", "failed") else None
        result["outcome"] = "done" if task_ok else ("failed" if task_status == "failed" else "ran")
        result["reply"] = f"Tâche qa {task_id} exécutée (status={task_status})"

        if persist:
            _save_state(
                {
                    "last_spawn_ts": time.time(),
                    "last_task_id": task_id,
                    "last_task_status": task_status,
                    "last_task_ok": task_ok,
                }
            )
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result["ok"] = False
        result["outcome"] = "error"
        result["error"] = str(exc)
        result["reply"] = f"Échec playbook smoke qa : {exc}"

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
