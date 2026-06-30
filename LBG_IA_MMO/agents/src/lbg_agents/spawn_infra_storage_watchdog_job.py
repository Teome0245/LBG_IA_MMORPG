"""Timer core 140 : sonde stockage Proxmox → job Pilot (#/jobs) si alerte."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from lbg_agents.proxmox_storage_probe import probe_proxmox_storage_local, thin_crit_pct, thin_warn_pct


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def jobs_enabled() -> bool:
    return _truthy(os.environ.get("LBG_STORAGE_WATCHDOG_JOBS_ENABLED", "1"))


def orchestrator_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").strip().rstrip("/")


def spawn_actor_id() -> str:
    return os.environ.get("LBG_STORAGE_WATCHDOG_ACTOR_ID", "system:storage_watchdog").strip()


def state_path() -> Path:
    raw = os.environ.get("LBG_STORAGE_WATCHDOG_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path("/var/lib/lbg/storage_watchdog/state.json")


def cooldown_s(outcome: str) -> float:
    if outcome == "critical":
        try:
            return max(300.0, float(os.environ.get("LBG_STORAGE_WATCHDOG_COOLDOWN_CRITICAL_S", "900")))
        except ValueError:
            return 900.0
    try:
        return max(600.0, float(os.environ.get("LBG_STORAGE_WATCHDOG_COOLDOWN_WARN_S", "1800")))
    except ValueError:
        return 1800.0


def default_objective() -> str:
    return os.environ.get(
        "LBG_STORAGE_WATCHDOG_OBJECTIVE",
        "Surveillance stockage Proxmox 201 local-lvm et Prime 246 — sonde thin pool, remédiation disque si alerte",
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


def _should_spawn(outcome: str, st: dict[str, Any]) -> bool:
    if outcome == "ok":
        return False
    last = float(st.get("last_spawn_ts") or 0)
    last_outcome = str(st.get("last_spawn_outcome") or "")
    if time.time() - last < cooldown_s(outcome):
        return False
    # Re-spawn plus tôt si aggravation warn → critical
    if outcome == "critical" and last_outcome == "warn":
        if time.time() - last >= cooldown_s("critical"):
            return True
    if last and time.time() - last < cooldown_s(outcome):
        return False
    return True


def _create_job(objective: str, *, storage: dict[str, Any]) -> dict[str, Any]:
    url = f"{orchestrator_url()}/v1/jobs"
    body = {
        "actor_id": spawn_actor_id(),
        "objective": objective,
        "auto_start": True,
        "context": {
            "_storage_watchdog_spawn": True,
            "devops_dry_run": False,
            "_storage_probe": storage,
        },
        "approval_token": os.environ.get("LBG_JOBS_APPROVAL_TOKEN", "").strip() or None,
    }
    # Retirer clés None pour JSON propre
    if body["approval_token"] is None:
        del body["approval_token"]
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_spawn(*, persist: bool = True) -> dict[str, Any]:
    if not jobs_enabled():
        return {"ok": True, "outcome": "skipped", "reply": "LBG_STORAGE_WATCHDOG_JOBS_ENABLED=0"}

    storage = probe_proxmox_storage_local()
    outcome = str(storage.get("outcome") or ("critical" if not storage.get("ok") else "ok"))
    st = _load_state() if persist else {}

    result: dict[str, Any] = {
        "ok": True,
        "agent": "spawn_infra_storage_watchdog_job",
        "outcome": outcome,
        "storage": storage,
        "thresholds": {"warn": thin_warn_pct(), "critical": thin_crit_pct()},
        "spawned": False,
        "job_id": None,
    }

    if _should_spawn(outcome, st):
        try:
            job = _create_job(default_objective(), storage=storage)
            job_id = job.get("id") if isinstance(job, dict) else None
            result["spawned"] = True
            result["job_id"] = job_id
            result["job_status"] = job.get("status") if isinstance(job, dict) else None
            result["reply"] = f"Job Pilot créé : {job_id} (outcome={outcome})"
            if persist:
                _save_state(
                    {
                        "last_spawn_ts": time.time(),
                        "last_spawn_outcome": outcome,
                        "last_job_id": job_id,
                        "last_data_percent": storage.get("data_percent"),
                    }
                )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
            result["reply"] = f"Échec création job orchestrateur : {exc}"
    else:
        result["reply"] = f"Sonde {outcome} — pas de nouveau job (cooldown ou OK)"

    if persist and not result.get("spawned"):
        st["last_check_ts"] = time.time()
        st["last_outcome"] = outcome
        st["last_data_percent"] = storage.get("data_percent")
        _save_state(st)

    return result


def main() -> int:
    result = run_spawn()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        return 3
    # warn/critical = sonde OK avec alerte — ne pas marquer l'unité systemd en failed
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
