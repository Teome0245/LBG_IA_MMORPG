"""Lecture feed ZB-1 — zone_bridge_live.json écrit par Core3 (20 Hz)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def zone_bridge_json_path() -> Path:
    raw = os.environ.get("LBG_GATEWAY_ZONE_BRIDGE_JSON", "").strip()
    if raw:
        return Path(raw)
    raw2 = os.environ.get("LBG_ZONE_BRIDGE_JSON_PATH", "").strip()
    if raw2:
        return Path(raw2)
    return Path("/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/zone_bridge_live.json")


def zone_bridge_live_enabled() -> bool:
    return os.environ.get("LBG_GATEWAY_ZONE_BRIDGE_LIVE", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def max_age_s() -> float:
    try:
        return max(0.5, float(os.environ.get("LBG_GATEWAY_ZONE_BRIDGE_MAX_AGE_S", "2.5")))
    except ValueError:
        return 2.5


def read_live_zone_state(*, path: Path | None = None, max_age: float | None = None) -> dict[str, Any] | None:
    """Lit le JSON ZB-1 si frais ; None si absent ou périmé."""
    if not zone_bridge_live_enabled():
        return None
    p = path or zone_bridge_json_path()
    if not p.is_file():
        return None
    try:
        age = time.time() - p.stat().st_mtime
    except OSError:
        return None
    limit = max_age if max_age is not None else max_age_s()
    if age > limit:
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("type") != "zone_state" or data.get("proto") != "lbg-ws/2":
        return None
    if not isinstance(data.get("entities"), list):
        return None
    data.setdefault("source", "zone_bridge_live")
    data["_feed_age_s"] = round(age, 3)
    return data


def merge_snapshot_entities(
    live: dict[str, Any],
    snapshot_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Si le feed live n'a pas d'entités, compléter avec snapshots gateway."""
    live_ents = live.get("entities")
    if isinstance(live_ents, list) and live_ents:
        return live_ents
    return snapshot_entities


def probe_zone_bridge_feed(*, path: Path | None = None) -> dict[str, Any]:
    p = path or zone_bridge_json_path()
    live = read_live_zone_state(path=p, max_age=max_age_s())
    checks: dict[str, Any] = {
        "json_path": str(p),
        "file_exists": p.is_file(),
        "live_enabled": zone_bridge_live_enabled(),
    }
    if p.is_file():
        try:
            checks["mtime_age_s"] = round(time.time() - p.stat().st_mtime, 3)
        except OSError:
            checks["mtime_age_s"] = None
    if live:
        checks["tick"] = live.get("tick")
        checks["zone"] = live.get("zone")
        checks["entity_count"] = len(live.get("entities") or [])
    ok = bool(checks.get("live_enabled")) and checks.get("file_exists") and live is not None
    gaps: list[str] = []
    if not checks.get("file_exists"):
        gaps.append("zone_bridge_live.json absent — compiler Core3 ZB-1 ou démarrer Prime")
    elif live is None:
        gaps.append("feed JSON périmé ou invalide — vérifier LBG_ZONE_BRIDGE_JSON_EXPORT sur Prime")
    return {
        "track": "zb1_live_feed",
        "ok": ok,
        "checks": checks,
        "gaps": gaps,
        "sample": live,
    }
