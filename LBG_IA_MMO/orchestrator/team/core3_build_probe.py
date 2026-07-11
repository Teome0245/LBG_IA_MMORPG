"""Sonde / plan build Core3 Antigravity (ZB-0) — dry-run par défaut."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_vm_host() -> str:
    return os.environ.get(
        "LBG_NEW_MMO_VM_HOST",
        os.environ.get("LBG_LAN_HOST_CORE3_PRIME", "192.168.0.246"),
    ).strip()


def build_script_path() -> Path:
    raw = os.environ.get("LBG_TEAM_CORE3_BUILD_SCRIPT", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "infra/scripts/build_core3_antigravity_vm.sh"


def install_script_path() -> Path:
    raw = os.environ.get("LBG_TEAM_CORE3_INSTALL_SCRIPT", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "infra/scripts/install_core3_clean_after_vm_build.sh"


def build_requires_approval() -> bool:
    return os.environ.get("LBG_TEAM_CORE3_BUILD_REQUIRES_APPROVAL", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def probe_core3_build_plan(*, execute: bool = False) -> dict[str, Any]:
    script = build_script_path()
    install = install_script_path()
    host = build_vm_host()
    ok = script.is_file()
    plan: dict[str, Any] = {
        "host": host,
        "build_script": str(script),
        "install_script": str(install),
        "steps": [
            f"rsync lbg-mmo → {host}:/opt/lbg-antigravity/lbg-mmo (--sync)",
            "cmake configure + build --target core3 (log /tmp/core3-antigravity-build.log)",
            f"install core3-clean → {install.name}",
            "restart lbg-core3-prime + smoke sidecar 246",
        ],
        "log_path": "/tmp/core3-antigravity-build.log",
        "dry_run": not execute,
        "requires_approval": build_requires_approval(),
    }
    if not ok:
        return {
            "track": "core3_build_plan",
            "ok": False,
            "error": f"Script build absent : {script}",
            "plan": plan,
        }
    return {
        "track": "core3_build_plan",
        "ok": True,
        "plan": plan,
        "execute_requested": execute,
    }


def run_core3_build(*, sync: bool = True, timeout_s: float | None = None) -> dict[str, Any]:
    script = build_script_path()
    if not script.is_file():
        return {"ok": False, "error": f"Script absent : {script}"}
    if timeout_s is None:
        try:
            timeout_s = float(os.environ.get("LBG_TEAM_CORE3_BUILD_TIMEOUT_S", "7200"))
        except ValueError:
            timeout_s = 7200.0
    args = ["bash", str(script)]
    if sync:
        args.append("--sync")
    host = build_vm_host()
    env = {**os.environ, "LBG_NEW_MMO_VM_HOST": host}
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=max(60.0, timeout_s),
            cwd=str(_repo_root()),
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "host": host,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-800:],
            "log_hint": f"ssh lbg@{host} tail -f /tmp/core3-antigravity-build.log",
        }
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or b"").decode("utf-8", errors="ignore")[-1500:]
        return {
            "ok": False,
            "timed_out": True,
            "host": host,
            "stdout_tail": partial,
            "hint": "Build long — vérifier le log sur la VM",
        }
    except (OSError, ValueError) as e:
        return {"ok": False, "error": str(e), "host": host}


def check_build_log_tail(host: str | None = None) -> dict[str, Any]:
    """Lecture read-only du log build sur la VM (ssh tail)."""
    h = (host or build_vm_host()).strip()
    cmd = f"tail -n 15 /tmp/core3-antigravity-build.log 2>/dev/null || echo '(log absent)'"
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"lbg@{h}", cmd],
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        text = (proc.stdout or "").strip()
        building = "[100%]" in text or "Built target core3" in text
        return {
            "ok": proc.returncode == 0,
            "host": h,
            "tail": text[-1200:],
            "build_complete_hint": building,
        }
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "host": h, "error": str(e)}
