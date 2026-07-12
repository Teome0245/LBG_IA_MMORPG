"""Remédiation auto M9 — exécute export/sync quand les sondes détectent des gaps M9a."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prime_client_root() -> Path:
    raw = os.environ.get("LBG_PRIME_CLIENT_ROOT", "").strip()
    if raw:
        return Path(raw)
    new_mmo = os.environ.get("LBG_NEW_MMO_ROOT", "").strip()
    if new_mmo:
        candidate = Path(new_mmo) / "prime-client"
        if candidate.is_dir():
            return candidate
    for candidate in (
        Path("/home/sdesh/projects/new_mmo/prime-client"),
        Path("/opt/new_mmo/prime-client"),
    ):
        if candidate.is_dir():
            return candidate
    return Path("/home/sdesh/projects/new_mmo/prime-client")


def remediation_enabled() -> bool:
    return os.environ.get("LBG_TEAM_M9_AUTO_REMEDIATE", "1").strip().lower() in ("1", "true", "yes", "on")


def try_m9a_auto_remediate() -> dict[str, Any]:
    """Lance export_scrapaltai_for_godot.py si repo + prime-client accessibles."""
    if not remediation_enabled():
        return {"attempted": False, "skipped": True, "reason": "LBG_TEAM_M9_AUTO_REMEDIATE=0"}

    root = _repo_root()
    export_py = root / "tools/map_export/export_scrapaltai_for_godot.py"
    prime = _prime_client_root()
    sync_sh = root / "infra/scripts/sync_scrapaltai_poi_godot.sh"

    if not export_py.is_file():
        return {"attempted": False, "ok": False, "reason": "export_script_missing", "path": str(export_py)}

    prime.mkdir(parents=True, exist_ok=True)
    (prime / "assets/maps").mkdir(parents=True, exist_ok=True)

    actions: list[dict[str, Any]] = []
    ok = True

    for label, cmd in (
        ("export_full", [sys.executable, str(export_py), "--out", str(prime)]),
        ("sync_poi", ["bash", str(sync_sh)] if sync_sh.is_file() else None),
    ):
        if cmd is None:
            continue
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env={**os.environ, "LBG_PRIME_CLIENT_ROOT": str(prime)},
            )
            entry = {
                "action": label,
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-400:],
                "stderr_tail": (proc.stderr or "")[-400:],
            }
            actions.append(entry)
            if proc.returncode != 0:
                ok = False
        except (OSError, subprocess.TimeoutExpired) as exc:
            actions.append({"action": label, "error": str(exc)})
            ok = False

    return {
        "attempted": True,
        "ok": ok,
        "prime_client_root": str(prime),
        "actions": actions,
    }
