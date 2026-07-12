"""Exécution des rôles équipe virtuelle (phase A : ops, qa, pm)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from typing import Callable

from lbg_agents.dispatch import invoke_after_route

from team import store as team_store
from team.models import TeamTask
from team.core3_build_workflow import execute_core3_build_workflow, resolve_core3_build_workflow
from team.dev_game_workflow import execute_dev_game_workflow
from team.godot_client_tracks_workflow import (
    execute_godot_client_tracks_workflow,
    resolve_godot_client_tracks_workflow,
)
from team.m9_map_workflow import execute_m9_map_workflow, resolve_m9_map_workflow
from team.m9_map_followup import (
    auto_run_followup_tasks as m9_auto_run_followup,
    maybe_spawn_after_m9_failure,
)
from team.godot_client_workflow import execute_godot_client_workflow, resolve_godot_client_workflow
from team.godot_dev_workflow import execute_godot_dev_workflow, resolve_godot_dev_workflow
from team.godot_followup import auto_run_followup_tasks as godot_auto_run_followup
from team.godot_followup import maybe_spawn_after_godot_failure
from team.godot_supervisor import execute_godot_supervisor
from team.godot_validation_workflow import execute_godot_validation_workflow, resolve_godot_validation_workflow
from team.infographiste_workflow import execute_infographiste_workflow, resolve_infographiste_workflow
from team.player_ia_exec import execute_player_ia
from team.qa_followup import auto_run_followup_tasks, maybe_spawn_after_qa_failure
from team.autoconsult_workflow import execute_autoconsult_workflow, resolve_autoconsult_workflow
from team.role_aliases import role_display

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
    "dev_godot": {
        "capability": "godot_dev_ia",
        "routed_to": "agent.pm",
        "autonomy": "L0-L1",
        "default_objective": "Audit / prototype Godot Prime — Iris (2D UI) ou Hermès (SOE/gateway)",
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

    if ctx.get("m9_ops_sync") or ops_kind == "m9_prime_sync":
        if os.environ.get("LBG_TEAM_OPS_USE_OPENCLAW", "1").strip().lower() in ("1", "true", "yes", "on"):
            from team.openclaw_adapter import run_ops_playbook

            out = run_ops_playbook("m9_prime_sync")
            out["kind"] = "ops_m9_sync"
            return out
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        script = root / "infra/scripts/sync_prime_client_assets_vm.sh"
        if not script.is_file():
            return {"kind": "ops_m9_sync", "ok": False, "error": f"script absent: {script}"}
        try:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            ok = proc.returncode == 0
            return {
                "kind": "ops_m9_sync",
                "ok": ok,
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-500:],
                "stderr_tail": (proc.stderr or "")[-500:],
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"kind": "ops_m9_sync", "ok": False, "error": str(exc)}

    if ops_kind in ("ollama", "ollama_audit") or ctx.get("ollama_audit"):
        from team.ollama_audit import audit_ollama_lan

        return {"kind": "ops_ollama_audit", **audit_ollama_lan()}

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
    if resolve_godot_validation_workflow(task):
        return execute_godot_validation_workflow(task)
    if task.context.get("godot_supervisor") or str(task.context.get("godot_mode", "")).strip().lower() in (
        "full",
        "supervisor",
        "sidecar",
        "gateway",
        "audit",
    ):
        return execute_godot_supervisor(task)

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
    if resolve_autoconsult_workflow(task):
        return execute_autoconsult_workflow(task, _dispatch)

    from team.subprojects import list_subprojects

    ctx = dict(task.context)
    ctx.setdefault("pm_focus", True)
    ctx.setdefault("project_pm", {"include_plan": True, "include_structure": True})
    reunification = bool(
        ctx.get("reunification_brief")
        or ctx.get("_team_pm_reunification_spawn")
        or re.search(r"\b(réunification|reunification|sous-projets?|thémis)\b", task.objective, re.I)
    )
    if reunification:
        ctx.setdefault("pm_include_plan", True)
        ctx.setdefault("pm_include_structure", True)
        ctx["reunification_brief"] = True
        ctx["subprojects"] = list_subprojects()
    out = _dispatch(
        "agent.pm",
        actor_id=task.actor_id,
        text=task.objective,
        context=ctx,
    )
    result: dict[str, object] = {"kind": "pm_brief", "output": out, "ok": True}
    if reunification:
        result["reunification"] = True
        result["subprojects_count"] = len(ctx.get("subprojects") or [])
    return result


def _execute_dev_godot(task: TeamTask) -> dict[str, object]:
    if resolve_godot_dev_workflow(task):
        return execute_godot_dev_workflow(task, _dispatch)
    return execute_godot_dev_workflow(task, _dispatch)


def _execute_dev_game(task: TeamTask) -> dict[str, object]:
    if resolve_infographiste_workflow(task):
        return execute_infographiste_workflow(task, _dispatch)
    if resolve_core3_build_workflow(task):
        return execute_core3_build_workflow(task, _dispatch)
    if resolve_m9_map_workflow(task):
        return execute_m9_map_workflow(task, _dispatch)
    if resolve_godot_client_tracks_workflow(task):
        return execute_godot_client_tracks_workflow(task, _dispatch)
    if resolve_godot_client_workflow(task):
        return execute_godot_client_workflow(task, _dispatch)
    return execute_dev_game_workflow(task, _dispatch)


def _execute_player_ia(task: TeamTask) -> dict[str, object]:
    return execute_player_ia(task)


_EXECUTORS: dict[str, Callable[[TeamTask], dict[str, object]]] = {
    "ops": _execute_ops,
    "qa": _execute_qa,
    "pm": _execute_pm,
    "dev_game": _execute_dev_game,
    "dev_godot": _execute_dev_godot,
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
                **{k: v for k, v in role_display(role).items() if k in ("alias", "title", "label")},
            }
        )

    if any(k in text for k in ("infra", "proxmox", "vm", "ollama", "ops", "sonde", "disque")):
        obj = objective if "ops" in text else str(ROLE_SPECS["ops"]["default_objective"])
        _add("ops", obj)
    if any(k in text for k in ("qa", "smoke", "test", "valide", "vérif", "verif", "lan")):
        obj = objective if "qa" in text else str(ROLE_SPECS["qa"]["default_objective"])
        _add("qa", obj)
    if any(k in text for k in ("pm", "jalon", "roadmap", "plan", "projet", "tâche", "tache", "réunification", "reunification", "sous-projet")):
        obj = objective if "pm" in text or "réunification" in text or "reunification" in text else str(ROLE_SPECS["pm"]["default_objective"])
        _add("pm", obj)
    if any(k in text for k in ("dev", "game", "gameplay", "bug", "correctif", "mmo", "core3")):
        obj = objective if any(k in text for k in ("dev", "bug", "game")) else str(ROLE_SPECS["dev_game"]["default_objective"])
        _add("dev_game", obj)
    if any(k in text for k in ("joueur", "joueurs", "lia", "nix", "bot", "player_ia", "prime", "246")):
        obj = objective if "joueur" in text or "lia" in text else str(ROLE_SPECS["player_ia"]["default_objective"])
        _add("player_ia", obj)
    if any(k in text for k in ("godot", "lbg-ws", "lbg_ws", "prime-client", "gateway", "zone.bridge")):
        qa_obj = objective if "godot" in text or "lbg" in text else "Supervise client Godot + sidecar 246 + readiness lbg-ws/2"
        proposals.append(
            {
                "role": "qa",
                "objective": qa_obj,
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": "team.qa",
                "context": {"godot_supervisor": True, "godot_mode": "full"},
                **{k: v for k, v in role_display("qa").items() if k in ("alias", "title", "label")},
            }
        )
        dev_obj = objective if "lbg" in text else "Audit lbg-ws/2 et proposition correctif client Godot Core3"
        proposals.append(
            {
                "role": "dev_game",
                "objective": dev_obj,
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"godot_track": "lbg_ws2"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("infographiste", "infograph", "glb", "blender", "pipeline assets", "assets 3d")):
        igo = objective if "infograph" in text or "glb" in text else "Audit pipeline assets GLB — manifest Godot et prochain export Blender"
        proposals.append(
            {
                "role": "dev_game",
                "objective": igo,
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"infographiste_ia": True, "subproject": "infographiste_ia"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("soe m3", "soe_m3", "soe live", "soe udp", "soe_handshake")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "soe" in text else "Audit SOE M3 — login + zone Godot Prime UDP",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"godot_track": "soe_m3", "subproject": "client_godot"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("soe m5", "soe_m5", "m5 play", "zqsd", "prime_controller")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "m5" in text or "play" in text else "Audit SOE M5 — play ZQSD prime_controller",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"godot_track": "soe_m5", "subproject": "client_godot"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("zb-0", "zb0", "zone bridge", "lbgzonebridge", "zone_bridge")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "zb" in text or "bridge" in text else "Audit ZB-0 LbgZoneBridge C++ readiness",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"godot_track": "zb0", "subproject": "client_godot"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("client live", "m3 m5", "godot live")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective,
                "priority": "high",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"godot_track": "client_live", "subproject": "client_godot"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("m9c", "carte m", "planet map", "waypoint", "locations tree")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "m9" in text or "carte" in text else "Audit M9c carte planétaire M + waypoints",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"m9_track": "m9c", "subproject": "prime_client_2d"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("m9b", "minimap", "mini map", "mini-map")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "minimap" in text else "Audit M9b minimap HUD style SWG",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"m9_track": "m9b", "subproject": "prime_client_2d"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("m9a", "scrapaltai", "planète scrapaltai", "planete scrapaltai")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "scrapaltai" in text else "Audit M9a Scrapaltai — texture planète + POI sync",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"m9_track": "m9a", "subproject": "prime_client_2d"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("jalon m9", "m9 map", "m9 scrapaltai", "map minimap")):
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "m9" in text else "Audit M9 complet — Scrapaltai 2D + minimap + carte M",
                "priority": "high",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"m9_track": "m9_full", "subproject": "prime_client_2d"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("autoconsult", "autoconsultation", "round fable", "round équipe", "round equipe")):
        proposals.append(
            {
                "role": "pm",
                "objective": objective if "autoconsult" in text else "Round autoconsultation équipe — synthèse Thémis",
                "priority": "high",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["pm"]["capability"],
                "context": {"autoconsult_round": True, "reunification_brief": True},
                **{k: v for k, v in role_display("pm").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("iris", "m9", "minimap", "carte m", "scrapaltai", "waypoint", "godot 2d")):
        proposals.append(
            {
                "role": "dev_godot",
                "objective": objective if "iris" in text or "m9" in text else "Iris — audit Godot 2D Prime Client (M9)",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_godot"]["capability"],
                "context": {"godot_dev_persona": "iris", "godot_dev_track": "m9_full", "subproject": "godot_iris"},
                **{k: v for k, v in role_display("dev_godot").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("hermes", "hermès", "soe m3", "soe m5", "lbg-ws", "gateway godot")):
        proposals.append(
            {
                "role": "dev_godot",
                "objective": objective if "hermes" in text or "soe" in text else "Hermès — audit SOE/gateway Godot Prime",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_godot"]["capability"],
                "context": {"godot_dev_persona": "hermes", "godot_dev_track": "client_live", "subproject": "godot_hermes"},
                **{k: v for k, v in role_display("dev_godot").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("valider godot", "validation godot", "validation client")):
        proposals.append(
            {
                "role": "qa",
                "objective": objective if "valider" in text else "Valider client Godot — smokes + checklist humain",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["qa"]["capability"],
                "context": {"godot_validation": True},
                **{k: v for k, v in role_display("qa").items() if k in ("alias", "title", "label")},
            }
        )
    if any(k in text for k in ("plan build", "build zb", "core3 build")) and "compiler" not in text:
        proposals.append(
            {
                "role": "dev_game",
                "objective": objective if "build" in text else "Plan build Core3 ZB-0 (dry-run)",
                "priority": "normal",
                "approval_required": False,
                "actor_id": actor_id,
                "capability": ROLE_SPECS["dev_game"]["capability"],
                "context": {"core3_build": True, "subproject": "core3_build"},
                **{k: v for k, v in role_display("dev_game").items() if k in ("alias", "title", "label")},
            }
        )

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
                res = refreshed.result if isinstance(refreshed.result, dict) else {}
                if res.get("kind") == "godot_supervisor":
                    followups = maybe_spawn_after_godot_failure(refreshed)
                    if followups:
                        _trace_log(
                            {
                                "event": "godot_followup_spawned",
                                "task_id": task_id,
                                "followup_ids": followups,
                                "trace_id": trace_id,
                            }
                        )
                        godot_auto_run_followup(followups)
                else:
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
        elif task.role in ("dev_game", "dev_godot") and status == "failed":
            refreshed = team_store.get_task(task_id)
            if refreshed is not None:
                res = refreshed.result if isinstance(refreshed.result, dict) else {}
                kind = res.get("kind")
                if kind == "godot_dev_workflow":
                    track = str(res.get("godot_dev_track") or res.get("track") or "")
                    if track.startswith("m9"):
                        followups = maybe_spawn_after_m9_failure(refreshed)
                        if followups:
                            _trace_log(
                                {
                                    "event": "m9_followup_spawned",
                                    "task_id": task_id,
                                    "followup_ids": followups,
                                    "trace_id": trace_id,
                                }
                            )
                            m9_auto_run_followup(followups)
                elif kind == "m9_map_workflow":
                    followups = maybe_spawn_after_m9_failure(refreshed)
                    if followups:
                        _trace_log(
                            {
                                "event": "m9_followup_spawned",
                                "task_id": task_id,
                                "followup_ids": followups,
                                "trace_id": trace_id,
                            }
                        )
                        m9_auto_run_followup(followups)
                elif kind in ("godot_client_workflow", "godot_client_tracks_workflow"):
                    followups = maybe_spawn_after_godot_failure(refreshed)
                    if followups:
                        godot_auto_run_followup(followups)
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
