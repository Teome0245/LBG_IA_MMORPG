"""Timer core 140 : sonde stockage Proxmox → tâche équipe ``ops`` si warn/critical (L1)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
from pathlib import Path
from typing import Any

from lbg_agents.proxmox_storage_probe import probe_proxmox_storage_local, thin_crit_pct, thin_warn_pct
from lbg_agents.team_job_spawn import (
    cooldown_active,
    create_and_run_team_task,
    load_json_state,
    save_json_state,
    task_run_summary,
    truthy,
)


def job_enabled() -> bool:
    return truthy(os.environ.get("LBG_TEAM_OPS_STORAGE_JOB_ENABLED", "1"))


def spawn_actor_id() -> str:
    return os.environ.get("LBG_TEAM_OPS_STORAGE_JOB_ACTOR_ID", "system:team_ops_storage").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_TEAM_OPS_STORAGE_JOB_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/team_ops_storage/state.json")


def cooldown_s(outcome: str) -> float:
    if outcome == "critical":
        try:
            return max(300.0, float(os.environ.get("LBG_TEAM_OPS_STORAGE_COOLDOWN_CRITICAL_S", "900")))
        except ValueError:
            return 900.0
    try:
        return max(600.0, float(os.environ.get("LBG_TEAM_OPS_STORAGE_COOLDOWN_WARN_S", "1800")))
    except ValueError:
        return 1800.0


def default_objective(outcome: str) -> str:
    custom = os.environ.get("LBG_TEAM_OPS_STORAGE_JOB_OBJECTIVE", "").strip()
    if custom:
        return custom
    return (
        f"Sonde stockage Proxmox — alerte {outcome} "
        "(thin pool local-lvm / Prime — read-only L1)"
    )


def _should_spawn(outcome: str, st: dict[str, Any]) -> bool:
    if outcome == "ok":
        return truthy(os.environ.get("LBG_TEAM_OPS_STORAGE_SPAWN_ON_OK", "0"))
    last = float(st.get("last_spawn_ts") or 0)
    last_outcome = str(st.get("last_spawn_outcome") or "")
    if last and time.time() - last < cooldown_s(outcome):
        if outcome == last_outcome or outcome == "critical":
            return False
    return True


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not job_enabled():
        return {
            "ok": True,
            "outcome": "skipped",
            "reply": "LBG_TEAM_OPS_STORAGE_JOB_ENABLED=0",
            "spawned": False,
            "task_id": None,
        }

    storage = probe_proxmox_storage_local()
    outcome = str(storage.get("outcome") or ("critical" if not storage.get("ok") else "ok"))
    st = load_json_state(state_path()) if persist else {}

    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_team_ops_storage_job",
        "outcome": outcome,
        "storage": storage,
        "thresholds": {"warn": thin_warn_pct(), "critical": thin_crit_pct()},
        "spawned": False,
        "task_id": None,
    }

    if _should_spawn(outcome, st):
        try:
            payload = create_and_run_team_task(
                role="ops",
                objective=default_objective(outcome),
                actor_id=spawn_actor_id(),
                context={
                    "_team_ops_storage_spawn": True,
                    "ops_kind": "proxmox_storage",
                    "proxmox_storage": storage,
                },
            )
            summary = task_run_summary(payload)
            result["spawned"] = True
            result.update(summary)
            result["reply"] = f"Tâche ops {summary['task_id']} (status={summary['task_status']}, outcome={outcome})"
            if persist:
                save_json_state(
                    state_path(),
                    {
                        "last_spawn_ts": time.time(),
                        "last_spawn_outcome": outcome,
                        "last_task_id": summary["task_id"],
                        "last_data_percent": storage.get("data_percent"),
                    },
                )
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
            result["reply"] = f"Échec playbook ops stockage : {exc}"
    else:
        result["reply"] = f"Sonde {outcome} — pas de nouvelle tâche ops (OK ou cooldown)"

    if persist and not result.get("spawned"):
        st["last_check_ts"] = time.time()
        st["last_outcome"] = outcome
        st["last_data_percent"] = storage.get("data_percent")
        save_json_state(state_path(), st)

    return result


def main() -> int:
    result = run_spawn()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        return 3
    if result.get("task_status") == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
