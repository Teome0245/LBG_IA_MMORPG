"""Sondes SOE UDP Core3 Prime — jalons M3 (login/zone) et M5 (play ZQSD)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def soe_client_root() -> Path:
    raw = os.environ.get("LBG_CLIENT_PRIME_LBG_DIR", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/new_mmo/client-prime-lbg"),
        Path("/home/sdesh/projects/new_mmo/client-prime-lbg"),
    ):
        if (candidate / "soe_handshake.py").is_file():
            return candidate
    return Path("/home/sdesh/projects/new_mmo/client-prime-lbg")


def soe_host() -> str:
    return os.environ.get("LBG_SOE_HOST", os.environ.get("LBG_TEAM_GODOT_GATEWAY_HOST", "192.168.0.246")).strip()


def soe_login_port() -> int:
    try:
        return int(os.environ.get("LBG_SOE_LOGIN_PORT", "44553"))
    except ValueError:
        return 44553


def soe_user() -> str:
    return os.environ.get("LBG_SOE_USER", "Bot_IA").strip()


def soe_password() -> str:
    return os.environ.get("LBG_SOE_PASSWORD", "lbgiabot").strip()


def soe_m3_enabled() -> bool:
    return _truthy("LBG_TEAM_GODOT_SOE_M3", "1")


def soe_m5_enabled() -> bool:
    return _truthy("LBG_TEAM_GODOT_SOE_M5", "0")


def _soe_script() -> Path | None:
    script = soe_client_root() / "soe_handshake.py"
    return script if script.is_file() else None


def _run_soe(args: list[str], *, timeout_s: float) -> dict[str, Any]:
    script = _soe_script()
    if script is None:
        return {
            "ok": False,
            "skipped": True,
            "error": f"soe_handshake.py absent ({soe_client_root()})",
        }
    host = soe_host()
    base = [
        "python3",
        str(script),
        "--host",
        host,
        "--port",
        str(soe_login_port()),
        "--user",
        soe_user(),
        "--password",
        soe_password(),
    ]
    try:
        proc = subprocess.run(
            base + args,
            capture_output=True,
            text=True,
            timeout=max(5.0, timeout_s),
            cwd=str(soe_client_root()),
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "host": host,
            "stdout_tail": out[-1200:],
            "timed_out": proc.returncode == 124,
        }
    except subprocess.TimeoutExpired as e:
        partial = ""
        if e.stdout:
            partial += e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="ignore")
        if e.stderr:
            partial += e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "timed_out": True,
            "host": host,
            "stdout_tail": partial[-1200:],
            "error": "timeout",
        }
    except (OSError, ValueError) as e:
        return {"ok": False, "host": host, "error": str(e)}


def _login_ok(output: str) -> bool:
    return "[Login] OK connexion LoginServer terminee" in output


def _zone_ok(output: str) -> bool:
    return "[Zone] OK connexion ZoneServer etablie" in output or "SceneCreateObjectByName" in output


def _play_ok(output: str) -> bool:
    return "Contrôleur actif" in output or "[--play] Contrôleur actif" in output


def probe_soe_m3_login() -> dict[str, Any]:
    """M3a — login SOE sans connexion zone."""
    if not soe_m3_enabled():
        return {"track": "soe_m3_login", "ok": True, "skipped": True}
    run = _run_soe(["--no-zone"], timeout_s=float(os.environ.get("LBG_SOE_M3_LOGIN_TIMEOUT_S", "25")))
    if run.get("skipped"):
        return {"track": "soe_m3_login", **run}
    tail = str(run.get("stdout_tail") or "")
    ok = bool(run.get("ok")) and _login_ok(tail)
    return {
        "track": "soe_m3_login",
        "ok": ok,
        "host": run.get("host"),
        "exit_code": run.get("exit_code"),
        "login_ok": _login_ok(tail),
        "stdout_tail": tail[-400:],
        "hint": None if ok else "Vérifier LoginServer Prime :44553 et compte SOE",
    }


def probe_soe_m3_zone() -> dict[str, Any]:
    """M3b — connexion ZoneServer + bridge UDP Godot (lecture courte)."""
    if not soe_m3_enabled():
        return {"track": "soe_m3_zone", "ok": True, "skipped": True}
    timeout = float(os.environ.get("LBG_SOE_M3_ZONE_TIMEOUT_S", "35"))
    run = _run_soe(["--godot-port", "12345"], timeout_s=timeout)
    if run.get("skipped"):
        return {"track": "soe_m3_zone", **run}
    tail = str(run.get("stdout_tail") or "")
    ok = _zone_ok(tail) or (_login_ok(tail) and run.get("timed_out"))
    return {
        "track": "soe_m3_zone",
        "ok": ok,
        "host": run.get("host"),
        "zone_ok": _zone_ok(tail),
        "timed_out": bool(run.get("timed_out")),
        "stdout_tail": tail[-500:],
        "hint": None if ok else "ZoneServer :44563 ou SceneCreate — voir jalon_client_godot_sidecar_246.md",
    }


def probe_soe_m5_play() -> dict[str, Any]:
    """M5 — SOE + prime_controller (--play, timeout court)."""
    if not soe_m5_enabled():
        return {"track": "soe_m5_play", "ok": True, "skipped": True}
    timeout = float(os.environ.get("LBG_SOE_M5_PLAY_TIMEOUT_S", "55"))
    run = _run_soe(["--play", "--godot-port", "12345", "--cmd-port", "12346"], timeout_s=timeout)
    if run.get("skipped"):
        return {"track": "soe_m5_play", **run}
    tail = str(run.get("stdout_tail") or "")
    ok = _play_ok(tail) or (_zone_ok(tail) and run.get("timed_out"))
    return {
        "track": "soe_m5_play",
        "ok": ok,
        "host": run.get("host"),
        "play_ok": _play_ok(tail),
        "zone_ok": _zone_ok(tail),
        "timed_out": bool(run.get("timed_out")),
        "stdout_tail": tail[-500:],
        "hint": None if ok else "Activer --play après M3 OK ; ports UDP 12345/12346",
    }


def probe_soe_m3_combined() -> dict[str, Any]:
    login = probe_soe_m3_login()
    if not login.get("ok") and not login.get("skipped"):
        return login
    zone = probe_soe_m3_zone()
    return zone if zone.get("track") == "soe_m3_zone" else login
