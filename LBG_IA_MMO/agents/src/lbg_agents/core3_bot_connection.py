"""Reconnexion headless des joueurs IA (Lia, Nix, Mira…) via sidecar Prime."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import httpx

from lbg_agents.core3_players import Core3IaPlayer, get_ai_player, list_ai_players
from lbg_agents.core3_player_autonomy import fetch_snapshot, sidecar_base_url

_RECONNECT_STATE: dict[str, float] = {}

_DEFAULT_BOTS = ("lia", "nix", "mira", "kael")


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def bot_auto_connect_enabled() -> bool:
    return _truthy(os.environ.get("LBG_CORE3_BOT_AUTO_CONNECT", os.environ.get("LBG_CORE3_LIA_AUTO_CONNECT", "1")))


def bot_connect_wait_s() -> int:
    raw = os.environ.get("LBG_CORE3_BOT_CONNECT_WAIT_S", os.environ.get("LBG_CORE3_LIA_CONNECT_WAIT_S", "90")).strip()
    try:
        n = int(raw)
    except ValueError:
        n = 90
    return max(20, min(n, 300))


def reconnect_cooldown_s() -> int:
    raw = os.environ.get("LBG_CORE3_BOT_RECONNECT_COOLDOWN_S", "240").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 240
    return max(60, min(n, 3600))


def managed_bot_ids() -> tuple[str, ...]:
    raw = os.environ.get("LBG_CORE3_IA_BOTS", "lia,nix,mira,kael").strip()
    if not raw:
        return _DEFAULT_BOTS
    return tuple(p.strip().lower() for p in raw.split(",") if p.strip())


def prime_server_ready() -> bool:
    """Prime UP : systemd core3-prime actif + sidecar healthz."""
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "lbg-core3-prime.service"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.stdout.strip() != "active":
            return False
    except (OSError, subprocess.TimeoutExpired):
        return False
    base = sidecar_base_url()
    if not base:
        return True
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(f"{base.rstrip('/')}/healthz")
        if resp.status_code != 200:
            return False
        body = resp.json() if resp.content else {}
        return bool(isinstance(body, dict) and body.get("ok"))
    except (httpx.HTTPError, ValueError):
        return False


def snapshot_needs_force_reconnect(snap: dict[str, Any]) -> bool:
    """Client systemd actif mais absent du online-players.log (zombie)."""
    reason = str(snap.get("reason") or "").strip().lower()
    return reason in {"not_in_online_log", "snapshot_stale", "player_offline"}


def is_player_online(firstname: str) -> bool:
    snap = fetch_snapshot(firstname)
    if snap.get("online"):
        return True
    if snapshot_needs_force_reconnect(snap):
        return False
    return bool(snap.get("online"))


def _timeout(read_s: float) -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=max(30.0, read_s + 20.0), write=20.0, pool=10.0)


def _cooldown_active(player_id: str) -> bool:
    last = _RECONNECT_STATE.get(player_id, 0.0)
    return (time.monotonic() - last) < reconnect_cooldown_s()


def _mark_reconnect(player_id: str) -> None:
    _RECONNECT_STATE[player_id] = time.monotonic()


def connect_player(
    player_id: str,
    *,
    wait: bool = True,
    wait_s: int | None = None,
    force_restart: bool = False,
) -> dict[str, Any]:
    """Demande au sidecar de (re)lancer le core3client du joueur IA."""
    player = get_ai_player(player_id)
    base = sidecar_base_url()
    if not base:
        return {
            "ok": False,
            "outcome": "configuration_error",
            "player_id": player.id,
            "player": player.firstname,
            "error": "LBG_CORE3_IA_SIDECAR_URL non défini",
        }
    snap = fetch_snapshot(player.firstname)
    zombie = snapshot_needs_force_reconnect(snap)
    if zombie:
        force_restart = True

    if is_player_online(player.firstname) and not force_restart:
        return {
            "ok": True,
            "outcome": "already_online",
            "player_id": player.id,
            "player": player.firstname,
        }
    body: dict[str, Any] = {
        "player_id": player.id,
        "wait": wait,
        "wait_s": wait_s if wait_s is not None else bot_connect_wait_s(),
        "force_restart": force_restart,
    }
    try:
        with httpx.Client(timeout=_timeout(float(body["wait_s"]))) as client:
            resp = client.post(f"{base}/v1/player/connect", json=body)
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        ok = resp.status_code == 200 and bool(payload.get("ok"))
        payload.setdefault("http_status", resp.status_code)
        payload.setdefault("ok", ok)
        payload.setdefault("player_id", player.id)
        payload.setdefault("player", player.firstname)
        return payload
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "outcome": "sidecar_unreachable",
            "player_id": player.id,
            "player": player.firstname,
            "error": str(exc),
        }


def _post_connect_lines(player: Core3IaPlayer) -> list[str]:
    """Placement initial : Mos Eisley exterieur (Lia progresse entertainer/artisan librement)."""
    if player.id == "lia":
        return [
            "move_to|Lia|tatooine|3528|-4804|5|mos_eisley",
        ]
    if player.id == "nix":
        return [
            "move_to|Nix|tatooine|4749|-837|32|mos_eisley",
        ]
    if player.id == "mira":
        return [
            "move_to|Mira|tatooine|3520|-4810|5|mos_eisley",
        ]
    if player.id == "kael":
        return [
            "move_to|Kael|tatooine|3465|-4682|5|training_yard",
        ]
    return []


def enqueue_lines(lines: list[str], *, player: Core3IaPlayer) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base or not lines:
        return {"ok": True, "outcome": "noop", "n": 0}
    snap = fetch_snapshot(player.firstname)
    enqueued = 0
    errors: list[str] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 7:
            continue
        action = parts[0]
        message = parts[6] if action in {"housing_enter", "move_to"} else parts[6]
        body = {
            "action": action,
            "player": player.firstname,
            "zone": str(snap.get("zone") or "tatooine"),
            "x": float(snap.get("x") or 0),
            "y": float(snap.get("y") or 0),
            "z": float(snap.get("z") or 0),
            "message": message,
            "raw_line": line,
        }
        try:
            with httpx.Client(timeout=_timeout(20.0)) as client:
                resp = client.post(f"{base}/v1/enqueue", json=body)
            payload = resp.json() if resp.content else {}
            if resp.status_code == 200 and isinstance(payload, dict) and payload.get("ok"):
                enqueued += 1
            else:
                errors.append(str(payload.get("error") or resp.status_code))
        except httpx.HTTPError as exc:
            errors.append(str(exc))
    return {"ok": enqueued > 0 or not errors, "outcome": "ok" if enqueued else "partial", "enqueued": enqueued, "errors": errors}


def ensure_player_connected(
    player_id: str,
    *,
    force_restart: bool = False,
    apply_placement: bool = True,
) -> dict[str, Any]:
    """Reconnecte un bot si hors ligne (avec cooldown anti-boucle)."""
    player = get_ai_player(player_id)
    snap = fetch_snapshot(player.firstname)
    if snapshot_needs_force_reconnect(snap):
        force_restart = True

    if is_player_online(player.firstname) and not force_restart:
        return {"ok": True, "outcome": "already_online", "player_id": player.id, "player": player.firstname}

    if not bot_auto_connect_enabled():
        return {
            "ok": True,
            "outcome": "auto_connect_disabled",
            "player_id": player.id,
            "player": player.firstname,
        }

    if _cooldown_active(player.id) and not force_restart:
        return {
            "ok": True,
            "outcome": "reconnect_cooldown",
            "player_id": player.id,
            "player": player.firstname,
            "cooldown_s": reconnect_cooldown_s(),
        }

    _mark_reconnect(player.id)
    out = connect_player(player.id, wait=True, force_restart=force_restart)
    if out.get("ok") and apply_placement and out.get("outcome") in {"connected", "already_online"}:
        placement = enqueue_lines(_post_connect_lines(player), player=player)
        out["placement"] = placement
    return out


def ensure_ia_bots_online(*, force_restart: bool = False) -> dict[str, Any]:
    """Reconnecte les bots IA declares (LBG_CORE3_IA_BOTS) si Prime est UP."""
    if not prime_server_ready():
        return {
            "ok": False,
            "outcome": "prime_not_ready",
            "managed": list(managed_bot_ids()),
            "bots": {},
        }
    results: dict[str, Any] = {}
    ok = True
    for pid in managed_bot_ids():
        res = ensure_player_connected(pid, force_restart=force_restart)
        results[pid] = res
        if not res.get("ok") and res.get("outcome") not in {
            "already_online",
            "reconnect_cooldown",
            "auto_connect_disabled",
        }:
            ok = False
    return {"ok": ok, "bots": results, "managed": list(managed_bot_ids())}
