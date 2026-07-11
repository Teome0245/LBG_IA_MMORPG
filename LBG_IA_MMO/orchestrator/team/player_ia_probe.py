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


def probe_player_ia(task: TeamTask | None = None) -> dict[str, object]:
    """Healthz sidecar + snapshot par bot (read-only, phase D L1)."""
    base = sidecar_base_url()
    bots = list(managed_bot_ids())
    if task and isinstance(task.context.get("player_ia_bots"), list):
        extra = [str(x).strip().lower() for x in task.context["player_ia_bots"] if str(x).strip()]
        if extra:
            bots = extra

    checks: list[dict[str, object]] = []
    all_ok = True

    try:
        with httpx.Client(timeout=httpx.Timeout(12.0)) as client:
            try:
                hr = client.get(f"{base}/healthz")
                health_ok = hr.status_code == 200
                body = hr.json() if hr.content else {}
                if isinstance(body, dict) and body.get("ok") is False:
                    health_ok = False
                checks.append({"kind": "sidecar_healthz", "url": f"{base}/healthz", "ok": health_ok, "status": hr.status_code})
                all_ok = all_ok and health_ok
            except httpx.HTTPError as e:
                checks.append({"kind": "sidecar_healthz", "url": f"{base}/healthz", "ok": False, "error": str(e)})
                all_ok = False

            for bot in bots:
                url = f"{base}/v1/player-snapshot"
                try:
                    sr = client.get(url, params={"player": bot.capitalize()})
                    snap_ok = sr.status_code == 200
                    snap: dict[str, object] = {}
                    if sr.content:
                        try:
                            raw = sr.json()
                            if isinstance(raw, dict):
                                snap = raw
                        except ValueError:
                            snap_ok = False
                    online = bool(snap.get("online") or snap.get("connected"))
                    entry: dict[str, object] = {
                        "kind": "player_snapshot",
                        "player": bot,
                        "ok": snap_ok and online,
                        "online": online,
                        "status": sr.status_code,
                    }
                    if snap.get("zone"):
                        entry["zone"] = snap.get("zone")
                    checks.append(entry)
                    all_ok = all_ok and bool(entry["ok"])
                except httpx.HTTPError as e:
                    checks.append({"kind": "player_snapshot", "player": bot, "ok": False, "error": str(e)})
                    all_ok = False
    except httpx.HTTPError as e:
        return {"kind": "player_ia_probe", "ok": False, "error": str(e), "sidecar": base}

    online_count = sum(1 for c in checks if c.get("kind") == "player_snapshot" and c.get("ok"))
    return {
        "kind": "player_ia_probe",
        "ok": all_ok,
        "sidecar": base,
        "target_vm": "246-prime",
        "bots_checked": bots,
        "online_count": online_count,
        "checks": checks,
    }
