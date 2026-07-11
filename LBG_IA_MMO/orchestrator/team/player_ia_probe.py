"""Sonde L1 joueurs IA Core3 Prime (sidecar :8791, VM 246)."""

from __future__ import annotations

import os

import httpx

from team.models import TeamTask


def sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_SIDECAR_URL", "http://192.168.0.246:8791").strip().rstrip("/")


def managed_bot_ids() -> tuple[str, ...]:
    raw = os.environ.get("LBG_CORE3_IA_BOTS", "lia,nix,mira,kael").strip()
    if not raw:
        return ("lia", "nix")
    return tuple(p.strip().lower() for p in raw.split(",") if p.strip())


def required_bot_ids() -> frozenset[str]:
    raw = os.environ.get("LBG_TEAM_PLAYER_IA_REQUIRED_BOTS", "lia,nix").strip()
    if not raw:
        return frozenset({"lia", "nix"})
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def probe_player_ia(task: TeamTask | None = None) -> dict[str, object]:
    """Healthz sidecar + snapshot par bot (read-only, phase D L1)."""
    base = sidecar_base_url()
    bots = list(managed_bot_ids())
    if task and isinstance(task.context.get("player_ia_bots"), list):
        extra = [str(x).strip().lower() for x in task.context["player_ia_bots"] if str(x).strip()]
        if extra:
            bots = extra

    checks: list[dict[str, object]] = []
    health_ok = False
    required = required_bot_ids()

    try:
        with httpx.Client(timeout=httpx.Timeout(12.0)) as client:
            try:
                hr = client.get(f"{base}/healthz")
                health_ok = hr.status_code == 200
                body = hr.json() if hr.content else {}
                if isinstance(body, dict) and body.get("ok") is False:
                    health_ok = False
                checks.append({"kind": "sidecar_healthz", "url": f"{base}/healthz", "ok": health_ok, "status": hr.status_code})
            except httpx.HTTPError as e:
                checks.append({"kind": "sidecar_healthz", "url": f"{base}/healthz", "ok": False, "error": str(e)})

            for bot in bots:
                url = f"{base}/v1/player-snapshot"
                is_required = bot.lower() in required
                try:
                    sr = client.get(url, params={"player": bot.capitalize()})
                    snap_ok = sr.status_code == 200
                    snap: dict[str, object] = {}
                    if sr.content:
                        try:
                            raw = sr.json()
                            if isinstance(raw, dict):
                                inner = raw.get("snapshot")
                                snap = inner if isinstance(inner, dict) else raw
                        except ValueError:
                            snap_ok = False
                    online = bool(snap.get("online") or snap.get("connected"))
                    bot_ok = snap_ok and online
                    entry: dict[str, object] = {
                        "kind": "player_snapshot",
                        "player": bot,
                        "required": is_required,
                        "ok": bot_ok if is_required else (True if not snap_ok else bot_ok),
                        "online": online,
                        "status": sr.status_code,
                    }
                    if not snap_ok and not is_required:
                        entry["ok"] = True
                        entry["skipped"] = True
                    if snap.get("zone"):
                        entry["zone"] = snap.get("zone")
                    checks.append(entry)
                except httpx.HTTPError as e:
                    checks.append(
                        {
                            "kind": "player_snapshot",
                            "player": bot,
                            "required": is_required,
                            "ok": False if is_required else True,
                            "skipped": not is_required,
                            "error": str(e),
                        }
                    )
    except httpx.HTTPError as e:
        return {"kind": "player_ia_probe", "ok": False, "error": str(e), "sidecar": base}

    online_count = sum(
        1 for c in checks if c.get("kind") == "player_snapshot" and c.get("online") and not c.get("skipped")
    )
    required_ok = all(c.get("ok") for c in checks if c.get("kind") == "player_snapshot" and c.get("required"))
    all_ok = health_ok and required_ok
    return {
        "kind": "player_ia_probe",
        "ok": all_ok,
        "sidecar": base,
        "target_vm": "246-prime",
        "bots_checked": bots,
        "online_count": online_count,
        "checks": checks,
    }
