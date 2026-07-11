"""Workflow qa — validation Godot bundle (smokes + résumé humain)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from team.godot_soe_probe import probe_soe_m3_login, soe_m3_enabled
from team.godot_supervisor import execute_godot_supervisor
from team.human_summary import format_validation_summary
from team.lbg_ws2_audit import audit_zb0_readiness
from team.models import TeamTask


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_godot_validation(task: TeamTask) -> bool:
    ctx = task.context
    if ctx.get("godot_validation") or ctx.get("validation_bundle"):
        return True
    text = (task.objective or "").lower()
    return bool(
        re.search(
            r"\b(valider|validation|checklist).*\b(godot|client|prime)\b"
            r"|\b(godot|client).*\b(valider|validation)\b",
            text,
        )
    )


def _run_smoke_script(name: str, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    script = _repo_root() / "infra/scripts" / name
    if not script.is_file():
        return {"track": f"smoke_{name}", "ok": True, "skipped": True, "note": "script absent"}
    env = {**os.environ, **(extra_env or {})}
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("LBG_TEAM_GODOT_VALIDATION_TIMEOUT_S", "90")),
            cwd=str(_repo_root()),
            env=env,
        )
        return {
            "track": f"smoke_{name.replace('.sh', '')}",
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-600:],
            "stderr_tail": (proc.stderr or "")[-300:],
        }
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"track": f"smoke_{name}", "ok": False, "error": str(e)}


def execute_godot_validation_workflow(task: TeamTask) -> dict[str, object]:
    supervisor = execute_godot_supervisor(
        TeamTask(
            id=task.id,
            role="qa",
            objective=task.objective,
            status="running",
            priority=task.priority,
            approval_required=False,
            actor_id=task.actor_id,
            context={**task.context, "godot_mode": "supervisor"},
        )
    )

    probes: list[dict[str, object]] = list(supervisor.get("tracks") or [])
    probes.append(audit_zb0_readiness())

    if soe_m3_enabled() and task.context.get("godot_validation_soe", True):
        probes.append(probe_soe_m3_login())

    if task.context.get("godot_validation_mirror", True):
        probes.append(_run_smoke_script("smoke_godot_sidecar_mirror_lan.sh"))

    required = [p for p in probes if isinstance(p, dict) and not p.get("skipped")]
    ok = all(p.get("ok") for p in required) if required else bool(supervisor.get("ok"))

    prime_path = os.environ.get(
        "LBG_GODOT_PRIME_CLIENT_PATH",
        "/home/sdesh/projects/new_mmo/prime-client",
    )
    lbg_path = _repo_root() / "lbg_client_godot"

    checklist = [
        f"Godot 2D Prime : godot4 --path {prime_path}",
        "Vérifier bots Lia/Nix sur la carte (miroir sidecar ou SOE M3)",
        f"Godot 3D LBG (optionnel) : godot4 --path {lbg_path}",
        "Si tout vert ci-dessus → approuver forge ou lancer build ZB-0 L2",
    ]

    human_summary = format_validation_summary(
        title="Argus — validation client Godot (checklist humain)",
        probes=probes,
        checklist=checklist,
    )

    return {
        "kind": "godot_validation_workflow",
        "ok": ok,
        "supervisor": supervisor,
        "probes": probes,
        "human_summary": human_summary,
        "subproject": "client_godot",
        "launch_commands": {
            "prime_2d": f"godot4 --path {prime_path}",
            "lbg_3d": f"godot4 --path {lbg_path}",
            "sidecar_mirror": "bash client-prime-lbg/run_sidecar_mirror.sh",
        },
    }


def resolve_godot_validation_workflow(task: TeamTask) -> bool:
    return _is_godot_validation(task)
