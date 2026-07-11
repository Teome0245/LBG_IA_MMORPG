"""Superviseur Godot + sidecar 246 + readiness lbg-ws/2 (phase D autonome)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from team.godot_soe_probe import probe_soe_m3_login, probe_soe_m3_zone, probe_soe_m5_play, soe_m3_enabled, soe_m5_enabled
from team.lbg_ws2_audit import audit_zb0_readiness
from team.models import TeamTask
from team.player_ia_probe import managed_bot_ids, probe_player_ia, required_bot_ids, sidecar_base_url


def supervisor_enabled() -> bool:
    return os.environ.get("LBG_TEAM_GODOT_SUPERVISOR_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def gateway_smoke_enabled() -> bool:
    return os.environ.get("LBG_TEAM_GODOT_GATEWAY_SMOKE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def gateway_host() -> str:
    return os.environ.get("LBG_TEAM_GODOT_GATEWAY_HOST", "192.168.0.246").strip()


def gateway_smoke_script() -> str:
    return os.environ.get("LBG_TEAM_GODOT_GATEWAY_SMOKE_SCRIPT", "").strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _check_sidecar_track() -> dict[str, Any]:
    fake_task = TeamTask(
        id="godot-supervisor",
        role="player_ia",
        objective="godot supervisor sidecar",
        status="running",
        priority="normal",
        approval_required=False,
        actor_id="system:godot_supervisor",
        context={},
    )
    out = probe_player_ia(fake_task)
    return {
        "track": "sidecar_m1",
        "ok": bool(out.get("ok")),
        "sidecar": out.get("sidecar"),
        "online_count": out.get("online_count"),
        "checks": out.get("checks"),
    }


def _check_mirror_track() -> dict[str, Any]:
    """Valide que le sidecar expose assez de snapshots pour alimenter Godot (équivalent miroir M1)."""
    base = sidecar_base_url()
    entities = 0
    errors: list[str] = []
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
            for bot in managed_bot_ids()[:4]:
                try:
                    r = client.get(f"{base}/v1/player-snapshot", params={"player": bot.capitalize()})
                    if r.status_code != 200:
                        continue
                    data = r.json() if r.content else {}
                    snap = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else data
                    if isinstance(snap, dict) and (snap.get("online") or snap.get("connected")):
                        entities += 1
                except httpx.HTTPError as e:
                    errors.append(f"{bot}:{e}")
    except httpx.HTTPError as e:
        return {"track": "godot_mirror_m1", "ok": False, "error": str(e), "entities": 0}
    ok = entities >= 1
    return {
        "track": "godot_mirror_m1",
        "ok": ok,
        "entities": entities,
        "required_bots": sorted(required_bot_ids()),
        "errors": errors[:3],
    }


def _check_gateway_track() -> dict[str, Any]:
    if not gateway_smoke_enabled():
        return {"track": "gateway_ws1", "ok": True, "skipped": True}
    script = gateway_smoke_script()
    if not script:
        default = _repo_root() / "infra/scripts/smoke_lbg_gateway_prime.sh"
        script = str(default) if default.is_file() else ""
    if not script or not Path(script).is_file():
        return {
            "track": "gateway_ws1",
            "ok": True,
            "skipped": True,
            "note": "smoke gateway non configuré (LBG_TEAM_GODOT_GATEWAY_SMOKE_SCRIPT)",
        }
    host = gateway_host()
    try:
        proc = subprocess.run(
            ["bash", script, "--host", host],
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("LBG_TEAM_GODOT_GATEWAY_TIMEOUT_S", "45")),
            cwd=str(_repo_root()),
        )
        return {
            "track": "gateway_ws1",
            "ok": proc.returncode == 0,
            "host": host,
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-400:],
            "stderr_tail": (proc.stderr or "")[-200:],
        }
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"track": "gateway_ws1", "ok": False, "host": host, "error": str(e)}


def _check_lbg_ws2_readiness() -> dict[str, Any]:
    from team.lbg_ws2_audit import audit_lbg_ws2_readiness

    return audit_lbg_ws2_readiness()


def _check_infographiste_track() -> dict[str, Any]:
    from team.infographiste_probe import probe_infographiste_assets

    out = probe_infographiste_assets(None)
    return {
        "track": "infographiste_assets",
        "ok": bool(out.get("ok")),
        "readiness": out.get("readiness"),
        "glb_expected": out.get("glb_expected"),
        "glb_present": out.get("glb_present"),
        "glb_missing": (out.get("glb_missing") or [])[:8],
        "hint": out.get("hint"),
    }


def execute_godot_supervisor(task: TeamTask) -> dict[str, object]:
    """Exécute les pistes Godot en parallèle logique (sidecar, miroir, gateway, lbg-ws/2)."""
    if not supervisor_enabled():
        return {
            "kind": "godot_supervisor",
            "ok": False,
            "error": "LBG_TEAM_GODOT_SUPERVISOR_ENABLED=0",
        }

    mode = str(task.context.get("godot_mode") or "full").strip().lower()
    tracks: list[dict[str, Any]] = []

    if mode in ("full", "supervisor", "sidecar"):
        tracks.append(_check_sidecar_track())
        tracks.append(_check_mirror_track())
    if mode in ("full", "supervisor", "gateway") and gateway_smoke_enabled():
        tracks.append(_check_gateway_track())
    elif mode in ("full", "supervisor"):
        tracks.append(_check_gateway_track())
    if mode in ("full", "supervisor", "lbg_ws2", "audit"):
        tracks.append(_check_lbg_ws2_readiness())
    if mode in ("full", "supervisor", "infographiste", "assets"):
        tracks.append(_check_infographiste_track())
    if mode in ("soe_m3", "soe", "client_live") and soe_m3_enabled():
        tracks.append(probe_soe_m3_login())
        tracks.append(probe_soe_m3_zone())
    if mode in ("soe_m5", "m5", "client_live") and soe_m5_enabled():
        tracks.append(probe_soe_m5_play())
    if mode in ("full", "supervisor", "zb0", "zone_bridge", "client_live", "lbg_ws2", "audit"):
        tracks.append(audit_zb0_readiness())

    required = [t for t in tracks if not t.get("skipped")]
    sidecar_tracks = [t for t in required if t.get("track") in ("sidecar_m1", "godot_mirror_m1")]
    sidecar_ok = all(t.get("ok") for t in sidecar_tracks) if sidecar_tracks else True
    other_ok = all(t.get("ok") for t in required if t.get("track") not in ("sidecar_m1", "godot_mirror_m1"))
    all_ok = sidecar_ok and other_ok

    return {
        "kind": "godot_supervisor",
        "ok": all_ok,
        "mode": mode,
        "tracks": tracks,
        "sidecar_ok": sidecar_ok,
        "ts": time.time(),
        "subproject": "client_godot",
    }
