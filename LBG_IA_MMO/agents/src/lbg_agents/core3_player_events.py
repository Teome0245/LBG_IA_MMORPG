"""Perception sociale des joueurs IA Core3 (Phase H)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

_SOCIAL_ACTIONS = frozenset(
    {"interact", "say", "perform", "approach_player", "animate", "housing_enter", "move"}
)


def _sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791").strip().rstrip("/")


def _timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_CORE3_IA_TIMEOUT", "45").strip()
    try:
        read_s = max(5.0, float(raw))
    except ValueError:
        read_s = 45.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def _state_dir() -> Path:
    raw = os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR", "").strip()
    return Path(raw) if raw else Path("/tmp/lbg-core3-player-autonomy")


def _cursor_path(player_id: str) -> Path:
    safe = "".join(ch for ch in player_id.lower() if ch.isalnum() or ch in ("-", "_")) or "player"
    return _state_dir() / f"{safe}.last_event"


def _reactive_pause_path(player_id: str) -> Path:
    safe = "".join(ch for ch in player_id.lower() if ch.isalnum() or ch in ("-", "_")) or "player"
    return _state_dir() / f"{safe}.reactive_until"


def _proactive_pause_path(player_id: str) -> Path:
    safe = "".join(ch for ch in player_id.lower() if ch.isalnum() or ch in ("-", "_")) or "player"
    return _state_dir() / f"{safe}.proactive_until"


def _last_greet_path(player_id: str) -> Path:
    safe = "".join(ch for ch in player_id.lower() if ch.isalnum() or ch in ("-", "_")) or "player"
    return _state_dir() / f"{safe}.last_greet.json"


def load_last_event_id(player_id: str) -> str:
    try:
        return _cursor_path(player_id).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_last_event_id(player_id: str, event_id: str) -> None:
    if not event_id:
        return
    path = _cursor_path(player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(event_id, encoding="utf-8")


def fetch_social_events(player: str, *, after: str | None = None, limit: int = 20) -> dict[str, Any]:
    base = _sidecar_base_url()
    if not base:
        return {"ok": False, "events": [], "outcome": "sidecar_url_missing"}
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.get(
                f"{base}/v1/events",
                params={"player": player, "after": after or "", "limit": str(limit)},
            )
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        events = payload.get("events")
        if not isinstance(events, list):
            events = []
        return {**payload, "ok": resp.status_code == 200 and bool(payload.get("ok")), "events": events}
    except httpx.HTTPError as exc:
        return {"ok": False, "events": [], "outcome": "sidecar_unreachable", "error": str(exc)}


def _find_latest_inbound(events: list[dict[str, Any]], firstname: str) -> dict[str, Any] | None:
    wanted = firstname.strip().lower()
    for event in reversed(events):
        target = str(event.get("target") or "").strip().lower()
        actor = str(event.get("actor") or "").strip().lower()
        if target == wanted and actor and actor != wanted:
            return event
    return None


def peek_latest_inbound_event(player_id: str, firstname: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Dernier message entrant sans avancer le curseur (poll rapide)."""
    after = load_last_event_id(player_id)
    payload = fetch_social_events(firstname, after=after, limit=20)
    events = [ev for ev in payload.get("events", []) if isinstance(ev, dict)]
    return _find_latest_inbound(events, firstname), payload


def commit_inbound_event(player_id: str, event: dict[str, Any]) -> None:
    event_id = str(event.get("event_id") or "").strip()
    if event_id:
        save_last_event_id(player_id, event_id)


def reactive_pause_s() -> float:
    raw = os.environ.get("LBG_CORE3_PLAYER_REACTIVE_PAUSE_S", "120").strip()
    try:
        sec = float(raw)
    except ValueError:
        sec = 120.0
    return max(30.0, min(sec, 600.0))


def proactive_cooldown_s() -> float:
    raw = os.environ.get("LBG_CORE3_LIA_PROACTIVE_COOLDOWN_S", "180").strip()
    try:
        sec = float(raw)
    except ValueError:
        sec = 180.0
    return max(60.0, min(sec, 900.0))


def greet_cooldown_s() -> float:
    raw = os.environ.get("LBG_CORE3_LIA_GREET_COOLDOWN_S", "600").strip()
    try:
        sec = float(raw)
    except ValueError:
        sec = 600.0
    return max(120.0, min(sec, 3600.0))


def _read_pause_until(path: Path) -> float:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0.0


def mark_reactive_handled(player_id: str, *, pause_s: float | None = None) -> None:
    until = time.time() + (pause_s if pause_s is not None else reactive_pause_s())
    path = _reactive_pause_path(player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(until), encoding="utf-8")


def mark_proactive_action(player_id: str, *, pause_s: float | None = None) -> None:
    """Pause les ticks proactifs après une action sociale (interact/say/perform…)."""
    until = time.time() + (pause_s if pause_s is not None else proactive_cooldown_s())
    path = _proactive_pause_path(player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(until), encoding="utf-8")


def record_greet(player_id: str, target: str) -> None:
    target_s = (target or "").strip()
    if not target_s:
        return
    path = _last_greet_path(player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"target": target_s, "ts": time.time()}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def greet_recently_sent(player_id: str, target: str) -> bool:
    path = _last_greet_path(player_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    if str(data.get("target") or "").strip().lower() != (target or "").strip().lower():
        return False
    try:
        ts = float(data.get("ts") or 0)
    except (TypeError, ValueError):
        return False
    return time.time() - ts < greet_cooldown_s()


def _parse_action_line(line: str) -> tuple[str, str]:
    parts = (line or "").split("|")
    if not parts:
        return "", ""
    action = parts[0].strip().lower()
    message = parts[-1].strip().lower() if len(parts) >= 7 else ""
    return action, message


def _extract_greet_target(message: str) -> str | None:
    msg = (message or "").strip().lower()
    if not msg.startswith("greet:"):
        return None
    target = msg.split("greet:", 1)[1].strip().split(":")[0].strip()
    return target or None


def maybe_apply_social_cooldown(player_id: str, result: dict[str, Any]) -> None:
    """Après un tick réussi : cooldown proactif + trace du dernier greet."""
    if not isinstance(result, dict) or not result.get("ok"):
        return
    action = str(result.get("action") or "").strip().lower()
    line = str(result.get("line") or "")
    _, message = _parse_action_line(line)
    if not action and line:
        action, message = _parse_action_line(line)
    is_social = action in _SOCIAL_ACTIONS
    is_greet = "greet" in message or action == "interact" and message.startswith("greet:")
    if not is_social and not is_greet:
        sidecar = result.get("sidecar")
        if isinstance(sidecar, dict):
            action = str(sidecar.get("action") or action).strip().lower()
            line = str(sidecar.get("line") or line)
            _, message = _parse_action_line(line)
            is_social = action in _SOCIAL_ACTIONS
            is_greet = "greet" in message
    if not is_social and not is_greet:
        return
    mark_proactive_action(player_id)
    greet_target = _extract_greet_target(message)
    if greet_target:
        record_greet(player_id, greet_target)
    elif action == "perform" and "greet" in message:
        record_greet(player_id, "_perform_greet")


def proactive_suppressed(player_id: str) -> bool:
    now = time.time()
    for path in (_reactive_pause_path(player_id), _proactive_pause_path(player_id)):
        if now < _read_pause_until(path):
            return True
    return False


def latest_inbound_event(player_id: str, firstname: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Compat : lit l'événement entrant et avance le curseur (préférer peek + commit)."""
    event, payload = peek_latest_inbound_event(player_id, firstname)
    if event is not None:
        commit_inbound_event(player_id, event)
    return event, payload


def event_prompt_block(event: dict[str, Any]) -> str:
    actor = str(event.get("actor") or "quelqu'un").strip()
    message = str(event.get("message") or event.get("source_line") or "").strip()
    event_type = str(event.get("type") or "core3.event").strip()
    return (
        f"Événement social récent ({event_type}) : {actor} s'adresse à toi. "
        f"Message/action: {message!r}. Réponds à {actor} en priorité, "
        "en francais naturel sans accents, en une phrase courte (maximum 16 mots). "
        "Si on te demande quoi faire, donne un objectif concret au lieu de reposer une question."
    )
