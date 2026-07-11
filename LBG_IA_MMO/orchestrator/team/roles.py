"""Exécution des rôles équipe virtuelle (phase A : ops, qa, pm)."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from typing import Callable

from lbg_agents.dispatch import invoke_after_route

from team import store as team_store
from team.models import TeamTask
from team.dev_game_workflow import execute_dev_game_workflow
from team.player_ia_probe import probe_player_ia
from team.qa_followup import auto_run_followup_tasks, maybe_spawn_after_qa_failure

Dispatcher = Callable[..., dict[str, object]]

_dispatch: Dispatcher = invoke_after_route

ROLE_SPECS: dict[str, dict[str, object]] = {
    "ops": {
        "capability": "devops_probe",
        "routed_to": "agent.devops",
        "autonomy": "L1",
        "default_objective": "Sonde santé orchestrateur et backend (read-only)",
    },
    "qa": {
        "capability": "team.qa",
        "routed_to": "agent.devops",
        "autonomy": "L1",
        "default_objective": "Smoke LAN read-only (healthz + systemd via script si configuré)",
    },
    "pm": {
        "capability": "project_pm",
        "routed_to": "agent.pm",
        "autonomy": "L0-L1",
        "default_objective": "Brief jalons et prochaines tâches projet",
    },
    "dev_game": {
        "capability": "prototype_game",
        "routed_to": "agent.pm",
        "autonomy": "L0-L1",
        "default_objective": "Analyser bug gameplay / correctif proposé (hors sandbox mmmorpg gelé)",
    },
    "player_ia": {
        "capability": "core3_bot_action",
        "routed_to": "agent.core3",
        "autonomy": "L1",
        "default_objective": "Sonde joueurs IA Core3 Prime (246) — sidecar + snapshots Lia/Nix",
    },
}


def _trace_log(event: dict[str, object]) -> None:
    path = os.environ.get("LBG_TEAM_TRACE_PATH", "").strip()
    if not path:
        state = team_store.db_path()
        parent = os.path.dirname(state) if state and state != ":memory:" else "."
        path = os.path.join(parent or ".", "team_trace.jsonl")
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        line = json.dumps({**event, "ts": time.time()}, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def approval_token_valid(token: str | None) -> bool:
    expected = os.environ.get("LBG_TEAM_APPROVAL_TOKEN", "").strip()
    if not expected:
        for fallback in (
            "LBG_DEVOPS_APPROVAL_TOKEN",
            "LBG_JOBS_APPROVAL_TOKEN",
        ):
            expected = os.environ.get(fallback, "").strip()
            if expected:
                break
    if not expected:
        return bool(token and str(token).strip())
    return bool(token and str(token).strip() == expected)


def _orchestrator_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_SELF_URL", "http://127.0.0.1:8010").rstrip("/")


def _backend_url() -> str:
    return os.environ.get("LBG_BACKEND_SELF_URL", "http://127.0.0.1:8000").rstrip("/")


def _qa_health_targets() -> list[str]:
    raw = os.environ.get(
        "LBG_TEAM_QA_HEALTH_URLS",
        f"{_orchestrator_url()}/healthz,{_backend_url()}/healthz",
    )
    return [u.strip() for u in raw.split(",") if u.strip()]


def _run_qa_smoke_script() -> dict[str, object]:
    script = os.environ.get("LBG_TEAM_QA_SMOKE_SCRIPT", "").strip()
    if not script or not os.path.isfile(script):
        return {"skipped": True, "reason": "LBG_TEAM_QA_SMOKE_SCRIPT non configuré"}
    timeout = int(os.environ.get("LBG_TEAM_QA_SMOKE_TIMEOUT_S", "120"))
    try:
        proc = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout après {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _execute_ops(task: TeamTask) -> dict[str, object]:
    ctx = dict(task.context)
    ops_kind = str(ctx.get("ops_kind") or "").strip().lower()

    storage = ctx.get("proxmox_storage")
    if ops_kind == "proxmox_storage" and isinstance(storage, dict):
        outcome = str(storage.get("outcome") or "ok")
        ok = outcome != "critical"
        return {"kind": "ops_storage", "storage": storage, "outcome": outcome, "ok": ok}

    if ops_kind == "ollama":
        import httpx

        url = str(ctx.get("ollama_tags_url") or "").strip()
        if not url:
            base = os.environ.get("LBG_TEAM_OPS_OLLAMA_URL", os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.110:11434"))
            url = base.strip().rstrip("/") + "/api/tags"
        try:
            timeout = float(os.environ.get("LBG_TEAM_OPS_OLLAMA_TIMEOUT_S", "8"))
            resp = httpx.get(url, timeout=timeout)
            ok = resp.status_code == 200
            body: dict[str, object] = {}
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    models = parsed.get("models")
                    body["model_count"] = len(models) if isinstance(models, list) else 0
            except Exception:
                pass
            return {
                "kind": "ops_ollama",
                "url": url,
                "status_code": resp.status_code,
                "body": body,
                "ok": ok,
            }
        except Exception as e:
            return {"kind": "ops_ollama", "url": url, "ok": False, "error": str(e)}

    orch = _orchestrator_url()
    action = ctx.get("devops_action")
    if not isinstance(action, dict):
        action = {"kind": "http_get", "url": f"{orch}/healthz"}
    ctx["devops_action"] = action
    ctx.setdefault("devops_dry_run", True)
    out = _dispatch(
        "agent.devops",
        actor_id=task.actor_id,
        text=task.objective,
        context=ctx,
    )
    return {"kind": "ops_probe", "output": out, "ok": bool(out.get("ok", True))}


def _execute_qa(task: TeamTask) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    all_ok = True
    for url in _qa_health_targets():
        ctx = {
            "devops_action": {"kind": "http_get", "url": url},
            "devops_dry_run": True,
        }
        out = _dispatch(
            "agent.devops",
            actor_id=task.actor_id,
            text=f"QA healthz {url}",
            context=ctx,
        )
        ok = bool(out.get("ok", False))
        if not ok:
            res = out.get("result")
            if isinstance(res, dict) and res.get("ok") is True:
                ok = True
        checks.append({"url": url, "ok": ok, "output": out})
        all_ok = all_ok and ok

    smoke = _run_qa_smoke_script()
    if smoke.get("skipped") is not True:
        all_ok = all_ok and bool(smoke.get("ok"))

    return {"kind": "qa_smoke", "health_checks": checks, "smoke_script": smoke, "ok": all_ok}


def _execute_pm(task: TeamTask) -> dict[str, object]:
    ctx = dict(task.context)
    ctx.setdefault("pm_focus", True)
    ctx.setdefault("project_pm", {"include_plan": True, "include_structure": True})
    out = _dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=ctx,
    )
    return {"kind": "pm_brief", "output": out, "ok": True}


def _execute_dev_game(task: TeamTask) -> dict[str, object]:
    return execute_dev_game_workflow(task, _dispatch)


def _execute_player_ia(task: TeamTask) -> dict[str, object]:
    return probe_player_ia(task)


_EXECUTORS: dict[str, Callable[[TeamTask], dict[str, object]]] = {
    "ops": _execute_ops,
    "qa": _execute_qa,
    "pm": _execute_pm,
    "dev_game": _execute_dev_game,
    "player_ia": _execute_player_ia,
}


def plan_from_objective(objective: str, *, actor_id: str = "system:team") -> list[dict[str, object]]:
    """Propose des tâches à partir d'un objectif NL (heuristique phase A)."""
    text = (objective or "").lower()
    proposals: list[dict[str, object]] = []

    def _add(role: str, obj: str) -> None:
        spec = ROLE_SPECS[role]
        proposals.append(
            {
                "role": role,
                "objective": obj,
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": spec["capability"],
            }
        )

    if any(k in text for k in ("infra", "proxmox", "vm", "ollama", "ops", "sonde", "disque")):
        obj = objective if "ops" in text else str(ROLE_SPECS["ops"]["default_objective"])
        _add("ops", obj)
    if any(k in text for k in ("qa", "smoke", "test", "valide", "vérif", "verif", "lan")):
        obj = objective if "qa" in text else str(ROLE_SPECS["qa"]["default_objective"])
        _add("qa", obj)
    if any(k in text for k in ("pm", "jalon", "roadmap", "plan", "projet", "tâche", "tache")):
        obj = objective if "pm" in text else str(ROLE_SPECS["pm"]["default_objective"])
        _add("pm", obj)
    if any(k in text for k in ("dev", "game", "gameplay", "bug", "correctif", "mmo", "core3")):
        obj = objective if any(k in text for k in ("dev", "bug", "game")) else str(ROLE_SPECS["dev_game"]["default_objective"])
        _add("dev_game", obj)
    if any(k in text for k in ("joueur", "joueurs", "lia", "nix", "bot", "player_ia", "prime", "246")):
        obj = objective if "joueur" in text or "lia" in text else str(ROLE_SPECS["player_ia"]["default_objective"])
        _add("player_ia", obj)

    if not proposals:
        _add("pm", objective)
        _add("qa", str(ROLE_SPECS["qa"]["default_objective"]))

    return proposals


def run_task(task_id: str, *, approval_token: str | None = None) -> TeamTask | None:
    task = team_store.get_task(task_id)
    if task is None:
        return None
    if task.status in ("done", "cancelled"):
        return task
    if task.status == "running":
        return task

    if task.approval_required and task.status != "review":
        if not approval_token_valid(approval_token or task.stored_approval_token):
            team_store.update_task(task_id, status="review")
            _trace_log({"event": "approval_required", "task_id": task_id, "role": task.role})
            return team_store.get_task(task_id)

    trace_id = task.trace_id or str(uuid.uuid4())
    team_store.update_task(task_id, status="running", context_patch={"trace_id": trace_id})
    _trace_log({"event": "run_start", "task_id": task_id, "role": task.role, "trace_id": trace_id})

    executor = _EXECUTORS.get(task.role)
    if executor is None:
        team_store.update_task(
            task_id,
            status="failed",
            result={"error": f"rôle non supporté: {task.role}"},
        )
        return team_store.get_task(task_id)

    try:
        result = executor(task)
        ok = bool(result.get("ok", True))
        status = "done" if ok else "failed"
        team_store.update_task(task_id, status=status, result=result)
        _trace_log({"event": "run_end", "task_id": task_id, "role": task.role, "ok": ok, "trace_id": trace_id})
        if task.role == "qa" and status == "failed":
            refreshed = team_store.get_task(task_id)
            if refreshed is not None:
                followups = maybe_spawn_after_qa_failure(refreshed)
                if followups:
                    _trace_log(
                        {
                            "event": "qa_followup_spawned",
                            "task_id": task_id,
                            "followup_ids": followups,
                            "trace_id": trace_id,
                        }
                    )
                    auto_run_followup_tasks(followups)
    except Exception as e:
        team_store.update_task(task_id, status="failed", result={"error": str(e)})
        _trace_log({"event": "run_error", "task_id": task_id, "error": str(e), "trace_id": trace_id})

    return team_store.get_task(task_id)


def approve_task(task_id: str, token: str) -> TeamTask | None:
    task = team_store.get_task(task_id)
    if task is None:
        return None
    if not approval_token_valid(token):
        team_store.update_task(
            task_id,
            result={**task.result, "approval_error": "token invalide"},
        )
        return team_store.get_task(task_id)
    team_store.update_task(
        task_id,
        status="queued",
        stored_approval_token=token,
        context_patch={"approved": True},
    )
    _trace_log({"event": "approved", "task_id": task_id})
    return team_store.get_task(task_id)


def cancel_task(task_id: str) -> TeamTask | None:
    task = team_store.get_task(task_id)
    if task is None:
        return None
    if task.status in ("done", "cancelled"):
        return task
    team_store.update_task(task_id, status="cancelled", result={**task.result, "cancelled": True})
    _trace_log({"event": "cancelled", "task_id": task_id})
    return team_store.get_task(task_id)


def set_dispatch_for_tests(fn: Dispatcher | None) -> None:
    global _dispatch
    _dispatch = fn or invoke_after_route  # type: ignore[assignment]
