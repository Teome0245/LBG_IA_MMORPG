"""Autonomie générique pour joueurs IA Core3 (Phase G)."""

from __future__ import annotations

import os
import re
import time
import unicodedata
from typing import Any

import httpx

from lbg_agents.core3_player_events import (
    commit_inbound_event,
    event_prompt_block,
    mark_reactive_handled,
    maybe_apply_social_cooldown,
    peek_latest_inbound_event,
    proactive_suppressed,
)
from lbg_agents.core3_players import Core3IaPlayer, get_ai_player, player_prompt_context


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def player_autonomy_enabled() -> bool:
    return _truthy(os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_ENABLED", "0"))


def player_autonomy_interval_s() -> int:
    raw = os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_INTERVAL_S", "35").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 35
    return max(15, min(n, 600))


def player_autonomy_poll_s() -> int:
    raw = os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_POLL_S", "3").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 3
    return max(2, min(n, 30))


def sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "http://127.0.0.1:8791").strip().rstrip("/")


def orchestrator_base_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_URL", "").strip().rstrip("/")


def player_autonomy_mode() -> str:
    raw = os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_MODE", "orchestrator").strip().lower()
    return raw if raw in {"orchestrator", "sidecar"} else "orchestrator"


def _timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_CORE3_IA_TIMEOUT", "45").strip()
    try:
        read_s = max(5.0, float(raw))
    except ValueError:
        read_s = 45.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def fetch_snapshot(firstname: str) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"online": False, "reason": "sidecar_url_missing"}
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.get(f"{base}/v1/player-snapshot", params={"player": firstname})
        payload = resp.json() if resp.content else {}
        snap = payload.get("snapshot") if isinstance(payload, dict) else {}
        if not isinstance(snap, dict):
            snap = {}
        if resp.status_code == 409 or not payload.get("ok"):
            snap.setdefault("online", False)
        return snap
    except httpx.HTTPError as exc:
        return {"online": False, "reason": "sidecar_unreachable", "detail": str(exc)}


def _relay_status(names: list[str]) -> str:
    parts: list[str] = []
    for name in names:
        snap = fetch_snapshot(name)
        state = "en ligne" if snap.get("online") else f"hors ligne ({snap.get('reason', 'offline')})"
        pos = ""
        if snap.get("online") and snap.get("x") is not None:
            pos = f" @({snap.get('x')},{snap.get('y')},{snap.get('z')})"
        parts.append(f"{name}: {state}{pos}")
    return "; ".join(parts)


def _tick_index() -> int:
    interval = player_autonomy_interval_s()
    raw = os.environ.get("LBG_CORE3_PLAYER_AUTONOMY_TICK", "").strip()
    if raw.isdigit():
        return int(raw)
    return int(time.time() // interval)


def _snapshot_flag(snapshot: dict[str, Any], key: str) -> bool:
    raw = snapshot.get(key)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _movement_guard(snapshot: dict[str, Any] | None, relays: list[str]) -> str:
    if not isinstance(snapshot, dict):
        return ""
    me_interior = _snapshot_flag(snapshot, "in_interior")
    hints: list[str] = []
    for name in relays:
        peer = fetch_snapshot(name)
        if not isinstance(peer, dict) or not peer.get("online"):
            continue
        if _snapshot_flag(peer, "in_interior") and not me_interior:
            hints.append(
                f"{name} est en interieur : pas de move_to exterieur ; "
                "approach_player seulement si tu es dans le meme batiment, sinon housing_enter ou say."
            )
            break
        if me_interior and _snapshot_flag(peer, "in_interior"):
            hints.append(
                "Tu es en interieur avec des allies proches : privilegie approach_player et interact, "
                "pas de move_to vers l exterieur."
            )
            break
    return " ".join(hints)


def _inventory_guard(snapshot: dict[str, Any] | None) -> str:
    if not isinstance(snapshot, dict):
        return ""
    if _snapshot_flag(snapshot, "inventory_full") or _snapshot_flag(snapshot, "inventory_near_full"):
        count = snapshot.get("inventory_count", "?")
        return (
            f"Inventaire presque plein ({count} objets) : interdiction de forage, "
            "pas de loot. Privilegie search, say, approach_player ou interact."
        )
    return ""


def build_player_prompt(player: Core3IaPlayer, *, tick_index: int | None = None) -> str:
    from lbg_agents.core3_behavior_profiles import build_player_scene_hint
    from lbg_agents.core3_economy_loop import economy_prompt_block, pick_economy_step
    from lbg_agents.core3_players import player_behavior_profile_id
    from lbg_agents.core3_profession_lifecycle import lifecycle_context_dict, tick_player_lifecycle
    from lbg_agents.core3_quest_autonomy import quest_prompt_block

    idx = _tick_index() if tick_index is None else tick_index
    life_view = tick_player_lifecycle(player, activity=False, persist=False)
    life_ctx = lifecycle_context_dict(player, activity=True)
    context = player_prompt_context(player)
    relays = ["Gally", "Lia"] if player.firstname.lower() != "lia" else ["Gally"]
    relay_block = _relay_status(relays)
    snap = fetch_snapshot(player.firstname)
    inv_guard = _inventory_guard(snap)
    move_guard = _movement_guard(snap, relays)

    profile_id = player_behavior_profile_id(player)
    in_interior = _snapshot_flag(snap, "in_interior") if isinstance(snap, dict) else False
    focus = life_ctx.get("focus_profession") or life_ctx.get("profession_current") or player.profession_current
    action_hint = build_player_scene_hint(
        profile_id,
        idx,
        inventory_full=bool(inv_guard),
        context={
            "profession_secondary": life_ctx.get("profession_secondary") or player.profession_secondary or "artisan",
            "profession_current": life_ctx.get("profession_current") or player.profession_current or "",
            "focus_profession": focus,
            **life_ctx,
        },
        in_interior=in_interior,
    )
    if not action_hint:
        action_hint = "perform message=think — tour autonome par defaut."
    inv_line = f" {inv_guard}" if inv_guard else ""
    move_line = f" {move_guard}" if move_guard else ""
    life_line = life_ctx.get("lifecycle_block", "")
    quest_line = quest_prompt_block(player)
    econ_step = pick_economy_step(player, snapshot=snap if isinstance(snap, dict) else {}, lifecycle=life_view)
    econ_line = economy_prompt_block(econ_step)
    return (
        f"{context} {life_line} {quest_line} {econ_line} Statut proches: {relay_block}.{inv_line}{move_line} "
        f"Tour autonome joueur IA (vrai joueur, pas ancre PNJ). Action attendue: {action_hint} "
        "Réponds uniquement via le JSON d'action Core3. Evite noop, mais evite aussi de repeter les memes phrases."
    )


def build_reactive_prompt(player: Core3IaPlayer, event: dict[str, Any]) -> str:
    context = player_prompt_context(player)
    relays = ["Gally", "Lia", "Nix"]
    relays = [name for name in relays if name.lower() != player.firstname.lower()]
    relay_block = _relay_status(relays)
    return (
        f"{context} Statut proches: {relay_block}. "
        f"{event_prompt_block(event)} "
        "Tu es incarné dans le jeu : réponds naturellement, évite noop, "
        "et utilise say/interact/approach_player/perform selon le besoin. Message sans accents."
    )


def route_context_for_player(player: Core3IaPlayer, prompt: str) -> dict[str, Any]:
    from lbg_agents.core3_profession_lifecycle import lifecycle_context_dict

    life = lifecycle_context_dict(player, activity=False)
    return {
        "core3_action": {
            "kind": "player_think",
            "player": player.firstname,
            "prompt": prompt,
            "enqueue": True,
            "incarnation": player.id == "lia",
        },
        "core3_player_id": player.id,
        "core3_player_role": player.role,
        "core3_profession_current": life.get("profession_current") or player.profession_current,
        "core3_profession_dynamic": player.profession_dynamic,
        "core3_profession_lifecycle": life,
        "core3_capabilities": list(player.capabilities),
        "core3_autonomy": True,
        "lia_incarnation": player.id == "lia",
    }


def think_via_sidecar(player: Core3IaPlayer, prompt: str) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "error": "LBG_CORE3_IA_SIDECAR_URL non défini"}
    body = {
        "prompt": prompt,
        "player": player.firstname,
        "enqueue": True,
        "incarnation": player.id == "lia",
    }
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.post(f"{base}/v1/think", json=body)
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        ok = resp.status_code == 200 and bool(payload.get("ok"))
        return {
            "ok": ok,
            "outcome": "ok" if ok else "sidecar_error",
            "mode": "sidecar",
            "http_status": resp.status_code,
            "player_id": player.id,
            "player": player.firstname,
            "actor_id": player.actor_id,
            "action": payload.get("action"),
            "line": payload.get("line"),
            "sidecar": payload,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "outcome": "sidecar_unreachable", "error": str(exc), "player": player.firstname}


def _ascii_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def enqueue_direct_action(
    player: Core3IaPlayer,
    *,
    action: str,
    message: str,
    snapshot: dict[str, Any] | None = None,
    target_xyz: tuple[float, float, float] | None = None,
    enqueue_player: str | None = None,
) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "error": "LBG_CORE3_IA_SIDECAR_URL non défini"}
    snap = snapshot or {}
    body: dict[str, Any] = {
        "action": action,
        "player": (enqueue_player or player.firstname),
        "zone": str(snap.get("zone") or "tatooine"),
        "x": float(snap.get("x") or 0),
        "y": float(snap.get("y") or 0),
        "z": float(snap.get("z") or 0),
        "message": message,
    }
    if target_xyz is not None:
        body["x"], body["y"], body["z"] = target_xyz
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.post(f"{base}/v1/enqueue", json=body)
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        ok = resp.status_code == 200 and bool(payload.get("ok"))
        return {
            "ok": ok,
            "outcome": "ok" if ok else "sidecar_error",
            "mode": "deterministic_event",
            "http_status": resp.status_code,
            "player_id": player.id,
            "player": player.firstname,
            "actor_id": player.actor_id,
            "action": action,
            "line": payload.get("line"),
            "sidecar": payload,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "outcome": "sidecar_unreachable", "error": str(exc), "player": player.firstname}


def deterministic_social_event_action(
    player: Core3IaPlayer,
    event: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if str(event.get("type") or "") != "core3.player_spatial_chat":
        return None

    msg = _ascii_lower(str(event.get("message") or event.get("source_line") or ""))
    actor = re.sub(r"[^A-Za-z0-9_-]+", "", str(event.get("actor") or "Gally")) or "Gally"

    if any(word in msg for word in ("danse", "danser", "dance", "dancer")):
        out = enqueue_direct_action(player, action="perform", message="dance", snapshot=snapshot)
        out["reason"] = "event_dance_request"
        return out
    if any(word in msg for word in ("forage", "/forage", "fourrage")):
        if isinstance(snapshot, dict) and (
            _snapshot_flag(snapshot, "inventory_full") or _snapshot_flag(snapshot, "inventory_near_full")
        ):
            out = enqueue_direct_action(player, action="perform", message="search", snapshot=snapshot)
            out["reason"] = "event_forage_blocked_inventory_full"
            return out
        out = enqueue_direct_action(player, action="perform", message="forage", snapshot=snapshot)
        out["reason"] = "event_forage_request"
        return out
    if any(word in msg for word in ("fouille", "fouiller", "cherche", "chercher", "scan", "inspect")):
        out = enqueue_direct_action(player, action="perform", message="search", snapshot=snapshot)
        out["reason"] = "event_search_request"
        return out
    if any(word in msg for word in ("viens", "approche", "rejoins", "follow", "come")):
        out = enqueue_direct_action(player, action="approach_player", message=actor, snapshot=snapshot)
        out["reason"] = "event_approach_request"
        return out
    return None


def deterministic_proactive_action(
    player: Core3IaPlayer,
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Actions proactives sans LLM : quetes, economie, cycle metier, metiers."""
    from lbg_agents.core3_economy_loop import deterministic_economy_action
    from lbg_agents.core3_profession_lifecycle import deterministic_decay_action, tick_player_lifecycle
    from lbg_agents.core3_quest_autonomy import deterministic_quest_action

    snap = snapshot if isinstance(snapshot, dict) else {}
    life = tick_player_lifecycle(player, activity=True, persist=True)
    idx = _tick_index()

    decay = deterministic_decay_action(player, enqueue=enqueue_direct_action)
    if decay is not None:
        return decay

    if idx % 5 == 0:
        quest = deterministic_quest_action(player, snapshot=snap, enqueue=enqueue_direct_action)
        if quest is not None:
            return quest

    if idx % 3 != 2:
        econ = deterministic_economy_action(
            player, snapshot=snap, lifecycle=life, enqueue=enqueue_direct_action
        )
        if econ is not None:
            return econ

    in_interior = _snapshot_flag(snap, "in_interior")
    inv_blocked = _snapshot_flag(snap, "inventory_full") or _snapshot_flag(snap, "inventory_near_full")

    if player.id == "nix":
        if in_interior:
            out = enqueue_direct_action(
                player,
                action="move_to",
                message="mos_eisley",
                snapshot=snap,
                target_xyz=(4749.0, -837.0, 32.0),
            )
            out["reason"] = "proactive_exit_interior"
            return out
        if inv_blocked:
            out = enqueue_direct_action(player, action="perform", message="search", snapshot=snap)
            out["reason"] = "proactive_forage_blocked_inventory"
            return out
        out = enqueue_direct_action(player, action="perform", message="forage", snapshot=snap)
        out["reason"] = "proactive_scout_forage"
        return out

    if player.id == "mira":
        if in_interior:
            out = enqueue_direct_action(
                player,
                action="move_to",
                message="mos_eisley",
                snapshot=snap,
                target_xyz=(3520.0, -4810.0, 5.0),
            )
            out["reason"] = "proactive_exit_interior_gather"
            return out
        if inv_blocked:
            out = enqueue_direct_action(player, action="perform", message="search", snapshot=snap)
            out["reason"] = "proactive_gather_blocked_inventory"
            return out
        out = enqueue_direct_action(player, action="perform", message="forage", snapshot=snap)
        out["reason"] = "proactive_artisan_forage"
        return out

    if player.id == "kael":
        if in_interior:
            out = enqueue_direct_action(
                player,
                action="move_to",
                message="mos_eisley_training_yard",
                snapshot=snap,
                target_xyz=(3465.0, -4682.0, 5.0),
            )
            out["reason"] = "proactive_exit_interior_train"
            return out
        out = enqueue_direct_action(player, action="perform", message="forage", snapshot=snap)
        out["reason"] = "proactive_brawler_gather"
        return out

    return None


def think_via_orchestrator(player: Core3IaPlayer, prompt: str) -> dict[str, Any]:
    base = orchestrator_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "error": "LBG_ORCHESTRATOR_URL non défini"}
    body = {
        "actor_id": player.actor_id,
        "text": prompt,
        "context": route_context_for_player(player, prompt),
    }
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.post(f"{base}/v1/route", json=body)
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
        ok = resp.status_code == 200 and bool(output.get("ok"))
        return {
            "ok": ok,
            "outcome": "ok" if ok else "orchestrator_error",
            "mode": "orchestrator",
            "http_status": resp.status_code,
            "player_id": player.id,
            "player": player.firstname,
            "actor_id": player.actor_id,
            "intent": payload.get("intent"),
            "routed_to": payload.get("routed_to"),
            "action": output.get("action"),
            "line": output.get("line"),
            "output": output,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "outcome": "orchestrator_unreachable", "error": str(exc), "player": player.firstname}


def think_player(player: Core3IaPlayer, prompt: str, *, via: str | None = None) -> dict[str, Any]:
    mode = (via or player_autonomy_mode()).strip().lower()
    if mode == "sidecar":
        return think_via_sidecar(player, prompt)
    return think_via_orchestrator(player, prompt)


def player_autonomy_tick(player_id: str, *, via: str | None = None) -> dict[str, Any]:
    from lbg_agents.core3_bot_connection import ensure_player_connected

    player = get_ai_player(player_id)
    snap = fetch_snapshot(player.firstname)
    if not snap.get("online"):
        conn = ensure_player_connected(player_id)
        snap = fetch_snapshot(player.firstname)
        if not snap.get("online"):
            return {
                "ok": True,
                "outcome": "skipped_offline",
                "player_id": player.id,
                "player": player.firstname,
                "snapshot": snap,
                "connect": conn,
            }
    social_event, events_payload = peek_latest_inbound_event(player.id, player.firstname)
    direct = (
        deterministic_social_event_action(player, social_event, snapshot=snap)
        if social_event is not None
        else None
    )
    if direct is not None:
        result = direct
        prompt = ""
        commit_inbound_event(player.id, social_event)
        mark_reactive_handled(player.id)
    elif social_event is not None:
        prompt = build_reactive_prompt(player, social_event)
        result = think_player(player, prompt, via=via)
        commit_inbound_event(player.id, social_event)
        mark_reactive_handled(player.id)
    elif proactive_suppressed(player.id):
        return {
            "ok": True,
            "outcome": "skipped_proactive_cooldown",
            "player_id": player.id,
            "player": player.firstname,
            "snapshot": snap,
            "social_event": None,
            "events": {
                "ok": bool(events_payload.get("ok")),
                "count": 0,
                "last_event_id": events_payload.get("last_event_id"),
            },
        }
    else:
        direct = deterministic_proactive_action(player, snapshot=snap)
        if direct is not None and player.id in {"nix", "mira", "kael", "lia"}:
            prompt = ""
            result = direct
        else:
            prompt = build_player_prompt(player)
            result = think_player(player, prompt, via=via)
        maybe_apply_social_cooldown(player.id, result)
    result["snapshot"] = snap
    result["prompt"] = prompt
    result["social_event"] = social_event
    result["events"] = {
        "ok": bool(events_payload.get("ok")),
        "count": len(events_payload.get("events", [])) if isinstance(events_payload.get("events"), list) else 0,
        "last_event_id": events_payload.get("last_event_id"),
    }
    return result


def run_player_autonomy_loop(player_id: str) -> None:
    """Poll rapide des événements chat + tours proactifs espacés."""
    interval = player_autonomy_interval_s()
    poll = player_autonomy_poll_s()
    next_proactive = 0.0
    while True:
        player = get_ai_player(player_id)
        social_event, _ = peek_latest_inbound_event(player.id, player.firstname)
        now = time.monotonic()
        if social_event is not None:
            print(player_autonomy_tick(player_id), flush=True)
            next_proactive = now + interval
            time.sleep(poll)
            continue
        if now >= next_proactive:
            print(player_autonomy_tick(player_id), flush=True)
            next_proactive = now + interval
        time.sleep(poll)
