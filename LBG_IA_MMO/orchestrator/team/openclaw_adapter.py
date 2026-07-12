"""Adaptateur OpenClaw — skills d'exécution locale mappées aux playbooks ops LBG."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _skills_dir() -> Path:
    return _repo_root() / "infra" / "openclaw" / "skills"


def openclaw_enabled() -> bool:
    return os.environ.get("LBG_OPENCLAW_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def openclaw_base_url() -> str:
    return os.environ.get("LBG_OPENCLAW_BASE_URL", "").strip().rstrip("/")


_BUILTIN_SKILLS: dict[str, dict[str, Any]] = {
    "ops_qa_smoke_lan": {
        "script": "infra/scripts/smoke_vm_lan.sh",
        "description": "Smoke LAN read-only — healthz + systemd",
        "timeout_s": 120,
        "owner": "argus",
    },
    "ops_m9_prime_sync": {
        "script": "infra/scripts/sync_prime_client_assets_vm.sh",
        "description": "Sync assets Prime Client vers VM 140",
        "timeout_s": 180,
        "owner": "hephaistos",
    },
    "ops_m9_poi_sync": {
        "script": "infra/scripts/sync_scrapaltai_poi_godot.sh",
        "description": "Export + sync POI Scrapaltai vers Godot",
        "timeout_s": 120,
        "owner": "hephaistos",
    },
    "ops_storage_watchdog": {
        "script": "infra/scripts/smoke_devops_selfcheck_lan.sh",
        "description": "Selfcheck stockage / devops LAN",
        "timeout_s": 90,
        "owner": "hephaistos",
    },
    "ops_smoke_minimap": {
        "script": "infra/scripts/smoke_prime_client_minimap.sh",
        "description": "Smoke M9b minimap Prime Client",
        "timeout_s": 60,
        "owner": "iris",
    },
    "ops_smoke_planet_map": {
        "script": "infra/scripts/smoke_prime_client_planet_map.sh",
        "description": "Smoke M9c carte planétaire",
        "timeout_s": 60,
        "owner": "iris",
    },
    "ops_godot_sidecar_mirror": {
        "script": "infra/scripts/smoke_godot_sidecar_mirror_lan.sh",
        "description": "Smoke sidecar 246 + miroir Godot",
        "timeout_s": 90,
        "owner": "hermes",
    },
}


def load_skill_definitions() -> dict[str, dict[str, Any]]:
    skills = dict(_BUILTIN_SKILLS)
    root = _skills_dir()
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("id"):
                    skills[str(data["id"])] = {**data, "_source": path.name}
            except (OSError, json.JSONDecodeError):
                continue
    return skills


def list_skills() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for skill_id, meta in load_skill_definitions().items():
        out.append(
            {
                "id": skill_id,
                "description": meta.get("description", ""),
                "owner": meta.get("owner", "hephaistos"),
                "script": meta.get("script"),
                "openclaw_native": bool(meta.get("openclaw_native")),
            }
        )
    return out


def _run_bash_skill(meta: dict[str, Any], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    script_rel = str(meta.get("script") or "").strip()
    if not script_rel:
        return {"ok": False, "error": "skill sans script"}
    script = _repo_root() / script_rel
    if not script.is_file():
        return {"ok": False, "error": f"script absent: {script}"}
    timeout = int(meta.get("timeout_s") or os.environ.get("LBG_OPENCLAW_SKILL_TIMEOUT_S", "120"))
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, **(env or {})},
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
            "script": str(script),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout}s", "script": str(script)}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "script": str(script)}


def _run_openclaw_remote(skill_id: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    base = openclaw_base_url()
    if not base:
        return {"ok": False, "error": "LBG_OPENCLAW_BASE_URL non configuré", "skipped": True}
    url = f"{base}/v1/skills/{skill_id}/run"
    try:
        timeout = float(os.environ.get("LBG_OPENCLAW_TIMEOUT_S", "120"))
        with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
            resp = client.post(url, json=payload or {})
            ok = resp.status_code < 400
            body: Any = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            return {"ok": ok, "status": resp.status_code, "body": body, "transport": "openclaw_http"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "transport": "openclaw_http"}


def run_skill(skill_id: str, *, env: dict[str, str] | None = None, prefer_openclaw: bool | None = None) -> dict[str, Any]:
    """Exécute un skill — OpenClaw HTTP si configuré, sinon fallback bash local."""
    if not openclaw_enabled():
        return {"ok": False, "error": "LBG_OPENCLAW_ENABLED=0", "skipped": True}

    skills = load_skill_definitions()
    meta = skills.get(skill_id)
    if meta is None:
        return {"ok": False, "error": f"skill inconnu: {skill_id}"}

    use_remote = prefer_openclaw if prefer_openclaw is not None else bool(openclaw_base_url())
    started = time.time()

    if use_remote and openclaw_base_url():
        result = _run_openclaw_remote(skill_id, payload={"env": env or {}})
        result["skill_id"] = skill_id
        result["duration_s"] = time.time() - started
        # Bridge LBG (:18790) ou OpenClaw natif — accepter si pas skipped
        if not result.get("skipped"):
            return result

    local = _run_bash_skill(meta, env=env)
    local["skill_id"] = skill_id
    local["transport"] = "bash_fallback"
    local["duration_s"] = time.time() - started
    return local


def run_ops_playbook(ops_kind: str) -> dict[str, Any]:
    """Route ops_kind Héphaïstos vers un skill OpenClaw."""
    mapping = {
        "m9_prime_sync": "ops_m9_prime_sync",
        "m9_poi_sync": "ops_m9_poi_sync",
        "qa_smoke": "ops_qa_smoke_lan",
        "storage": "ops_storage_watchdog",
        "smoke_minimap": "ops_smoke_minimap",
        "smoke_planet_map": "ops_smoke_planet_map",
        "godot_sidecar": "ops_godot_sidecar_mirror",
    }
    skill_id = mapping.get(ops_kind.strip().lower())
    if not skill_id:
        return {"ok": False, "error": f"ops_kind sans skill: {ops_kind}"}
    out = run_skill(skill_id)
    out["kind"] = f"openclaw_{ops_kind}"
    return out
