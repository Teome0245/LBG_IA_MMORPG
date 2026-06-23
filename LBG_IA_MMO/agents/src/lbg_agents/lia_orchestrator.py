"""Lia = incarnation IG de l'orchestrateur LBG (prompts, brain, entendre un joueur)."""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx

_PERSONA_CACHE: dict[str, Any] | None = None


def orchestrator_base_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").strip().rstrip("/")


def persona_path() -> Path:
    raw = os.environ.get("LBG_LIA_PERSONA_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/lia_orchestrator_persona.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "lia_orchestrator_persona.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/lia_orchestrator_persona.json")


def load_persona() -> dict[str, Any]:
    global _PERSONA_CACHE
    if _PERSONA_CACHE is not None:
        return _PERSONA_CACHE
    path = persona_path()
    if not path.is_file():
        _PERSONA_CACHE = {
            "display_name": "Lia",
            "identity": ["Tu es Lia, incarnation de l'orchestrateur LBG en jeu."],
            "relay_players": ["Gally"],
        }
        return _PERSONA_CACHE
    _PERSONA_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _PERSONA_CACHE


def bot_player_name() -> str:
    return (
        os.environ.get("CORE3_IA_BOT_CHARACTER", "").strip()
        or os.environ.get("CORE3_IA_BOT_NAME", "Lia").strip()
        or "Lia"
    )


def relay_player_names() -> list[str]:
    persona = load_persona()
    raw = persona.get("relay_players")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    return ["Gally"]


def fetch_brain_status() -> dict[str, Any] | None:
    base = orchestrator_base_url()
    if not base:
        return None
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
            resp = client.get(f"{base}/v1/brain/status")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None
    except httpx.HTTPError:
        return None


def brain_context_block(brain: dict[str, Any] | None) -> str:
    if not brain:
        return ""
    intent = str(brain.get("intent") or "").strip()
    narrative = str(brain.get("narrative") or "").strip()
    gauges = brain.get("gauges")
    parts: list[str] = []
    if narrative:
        parts.append(f"État orchestrateur : {narrative}")
    if intent:
        parts.append(f"Intent brain : {intent}")
    if isinstance(gauges, dict) and gauges:
        g = ", ".join(f"{k}={v}" for k, v in list(gauges.items())[:4])
        parts.append(f"Jauges : {g}")
    return " ".join(parts)


def lia_system_prompt() -> str:
    persona = load_persona()
    lines = persona.get("identity")
    if isinstance(lines, list):
        identity = " ".join(str(x) for x in lines)
    else:
        identity = str(persona.get("role", "Tu es Lia, orchestrateur en jeu."))
    actions = str(persona.get("actions_hint", ""))
    proactivity = str(persona.get("proactivity", ""))
    try:
        from lbg_agents.lia_perform import perform_catalog_hint

        perform_hint = perform_catalog_hint()
    except Exception:
        perform_hint = "perform : message = id (dance, greet, search, forage, …)."
    try:
        from lbg_agents.lia_entertainer import macro_hint_for_prompt

        entertainer_hint = macro_hint_for_prompt()
    except Exception:
        entertainer_hint = ""
    return (
        f"{identity} {proactivity} {actions} {perform_hint} {entertainer_hint} "
        "interact : message = kind:target, kind parmi greet, offer_trade, accept_trade, invite_group, accept_group, request_duel, examine, assist. "
        "Règle : noop est rare — préfère interact, perform, approach_player, say ou animate. "
        "Réponds UNIQUEMENT en JSON : "
        '{"action":"say|move_to|animate|perform|interact|approach_player|switch_zone|noop",'
        '"zone":"tatooine","x":0,"y":0,"z":0,"message":""}.'
    )


def relay_players_online() -> list[str]:
    """Prénoms IG des relay actuellement en ligne (snapshot sidecar)."""
    online: list[str] = []
    for name in relay_player_names():
        snap = fetch_player_snapshot(name)
        if snap.get("online"):
            online.append(name)
    return online


def relay_status_block() -> str:
    relays = relay_player_names()
    online = relay_players_online()
    off = [n for n in relays if n not in online]
    parts = [f"Relay en ligne : {', '.join(online)}" if online else "Aucun relay en ligne"]
    if off:
        parts.append(f"hors ligne : {', '.join(off)}")
    return ". ".join(parts) + "."


def proactive_tick_index() -> int:
    raw = os.environ.get("LBG_CORE3_LIA_PROACTIVE_TICK", "").strip()
    if raw.isdigit():
        return int(raw)
    interval = int(os.environ.get("LBG_CORE3_LIA_AUTONOMY_INTERVAL_S", "30") or 30)
    return int(time.time() // max(15, interval))


def build_proactive_prompt(*, brain: dict[str, Any] | None = None, tick_index: int | None = None) -> str:
    from lbg_agents.core3_player_events import greet_recently_sent

    brain = brain if brain is not None else fetch_brain_status()
    block = brain_context_block(brain)
    relays = relay_player_names()
    online = relay_players_online()
    status = relay_status_block()
    idx = proactive_tick_index() if tick_index is None else tick_index
    first_online = online[0] if online else (relays[0] if relays else "Gally")

    from lbg_agents.core3_behavior_profiles import build_orchestrator_scene_hint, get_behavior_profile
    from lbg_agents.core3_players import get_ai_player, player_behavior_profile_id

    profile_id = player_behavior_profile_id(get_ai_player("lia"))
    profile = get_behavior_profile(profile_id)
    scenes_raw = profile.get("scenes") if isinstance(profile.get("scenes"), list) else []
    n_scenes = max(1, len(scenes_raw))
    scene_idx = idx % n_scenes
    snap = fetch_player_snapshot(bot_player_name())
    in_interior = bool(snap.get("in_interior")) if isinstance(snap, dict) else False
    from lbg_agents.core3_behavior_profiles import pick_orchestrator_scene_index

    lia = get_ai_player("lia")
    from lbg_agents.core3_profession_lifecycle import lifecycle_context_dict

    life_ctx = lifecycle_context_dict(lia, activity=True)
    focus = life_ctx.get("focus_profession") or life_ctx.get("profession_current") or ""
    scene_idx = pick_orchestrator_scene_index(
        profile_id, scene_idx, in_interior=in_interior, focus_profession=focus
    )
    base = build_orchestrator_scene_hint(
        profile_id,
        scene_idx,
        context={"status": status, "first_online": first_online, **life_ctx},
        in_interior=in_interior,
        focus_profession=focus,
    )
    if not base:
        base = f"Tour autonome. {status} perform message=think."
    if greet_recently_sent("lia", first_online):
        for _ in range(n_scenes):
            if scene_idx not in (0, 1):
                break
            scene_idx = (scene_idx + 1) % n_scenes
            base = build_orchestrator_scene_hint(
                profile_id,
                scene_idx,
                context={"status": status, "first_online": first_online},
            )
    if block:
        return f"{life_ctx.get('lifecycle_block', '')} {base} {block}"
    return f"{life_ctx.get('lifecycle_block', '')} {base}"


def build_hear_prompt(*, from_player: str, text: str, brain: dict[str, Any] | None = None) -> str:
    brain = brain if brain is not None else fetch_brain_status()
    block = brain_context_block(brain)
    who = (from_player or "un joueur").strip()
    msg = (text or "").strip()
    core = (
        f"Le joueur {who} te parle en jeu. Message : « {msg} ». "
        "Tu incarnes l'orchestrateur LBG : réponds en personnage (approach_player si besoin, puis say). "
        "Reste courte et utile ; tu peux orienter vers les PNJ pilotes IA ou l'exploration si pertinent."
    )
    if block:
        return f"{core} {block}"
    return core


def _ascii_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _post_sidecar_enqueue(
    *,
    action: str,
    message: str,
    player: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "error": "LBG_CORE3_IA_SIDECAR_URL non defini"}
    snap = snapshot or {}
    body: dict[str, Any] = {
        "action": action,
        "player": player or bot_player_name(),
        "zone": str(snap.get("zone") or "tatooine"),
        "x": float(snap.get("x") or 0),
        "y": float(snap.get("y") or 0),
        "z": float(snap.get("z") or 0),
        "message": message,
    }
    with httpx.Client(timeout=_sidecar_timeout()) as client:
        resp = client.post(f"{base}/v1/enqueue", json=body)
    payload = resp.json() if resp.content else {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "ok": resp.status_code == 200 and bool(payload.get("ok")),
        "outcome": "ok" if resp.status_code == 200 and payload.get("ok") else "sidecar_error",
        "http_status": resp.status_code,
        "mode": "deterministic_hear",
        "action": action,
        "line": payload.get("line"),
        "sidecar": payload,
        "incarnation": True,
    }


_DANCE_STYLE_ALIASES: dict[str, str] = {
    "basic": "basic",
    "basic2": "basic2",
    "formal": "formal",
    "formal2": "formal2",
    "classique": "formal",
    "lyrical": "lyrical",
    "lyrical2": "lyrical2",
    "lent": "lyrical",
    "lente": "lyrical",
    "popular": "popular",
    "popular2": "popular2",
    "pop": "popular",
    "rhythmic": "rhythmic",
    "rhythmic2": "rhythmic2",
    "exotic": "exotic",
    "exotic2": "exotic2",
    "exo": "exotic",
    "theatrical": "theatrical",
    "theatrical2": "theatrical2",
    "footloose": "footloose",
    "breakdance": "breakdance",
}


def _parse_dance_style_from_text(text: str) -> str:
    msg = _ascii_lower(text)
    for token in re.findall(r"[a-z0-9]+", msg):
        if token in _DANCE_STYLE_ALIASES:
            return _DANCE_STYLE_ALIASES[token]
    return ""


def deterministic_hear_action(
    *,
    from_player: str,
    text: str,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    msg = _ascii_lower(text)
    who = re.sub(r"[^A-Za-z0-9_-]+", "", from_player or "Gally") or "Gally"
    if any(word in msg for word in ("danse", "danser", "dance", "dancer")):
        style = _parse_dance_style_from_text(text)
        perform_msg = f"dance:{style}" if style else "dance"
        out = _post_sidecar_enqueue(action="perform", message=perform_msg, snapshot=snapshot)
        out["reason"] = "hear_dance_request"
        return out
    if any(word in msg for word in ("forage", "/forage", "fourrage")):
        out = _post_sidecar_enqueue(action="perform", message="forage", snapshot=snapshot)
        out["reason"] = "hear_forage_request"
        return out
    if any(word in msg for word in ("fouille", "fouiller", "cherche", "chercher", "scan", "inspect")):
        out = _post_sidecar_enqueue(action="perform", message="search", snapshot=snapshot)
        out["reason"] = "hear_search_request"
        return out
    if any(word in msg for word in ("viens", "approche", "rejoins", "follow", "come")):
        out = _post_sidecar_enqueue(action="approach_player", message=who, snapshot=snapshot)
        out["reason"] = "hear_approach_request"
        return out
    if any(word in msg for word in ("objectif", "mission", "coordonne", "coordonner", "que dois", "quoi faire")):
        prompt = (
            f"{who} demande une coordination. Reponds en say, sans accents, maximum 14 mots, "
            "avec un objectif concret de reconnaissance ou d'observation."
        )
        out = incarnate_player_think(prompt=prompt, via=os.environ.get("LBG_CORE3_LIA_HEAR_VIA"))
        out["reason"] = "hear_coordination_request"
        return out
    return None


def deterministic_proactive_action(*, snapshot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Tours Lia selon le profil orchestrateur (danse, artisan novice, commerce) — pas d'ancre Jax."""
    snap = snapshot if isinstance(snapshot, dict) else {}
    in_interior = str(snap.get("in_interior") or "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        parent = int(snap.get("parent_id") or 0)
    except (TypeError, ValueError):
        parent = 0
    in_cantina = in_interior and parent == 1082877
    in_training = in_interior and parent == 1189639

    from lbg_agents.core3_behavior_profiles import pick_orchestrator_scene_index, scene_at_index
    from lbg_agents.core3_players import get_ai_player, player_behavior_profile_id
    from lbg_agents.core3_profession_lifecycle import lifecycle_context_dict

    lia = get_ai_player("lia")
    life_ctx = lifecycle_context_dict(lia, activity=True)
    focus = life_ctx.get("focus_profession") or life_ctx.get("profession_current") or ""

    idx = proactive_tick_index()
    profile_id = player_behavior_profile_id(lia)
    scene_idx = pick_orchestrator_scene_index(
        profile_id, idx, in_interior=in_interior, focus_profession=focus
    )
    scene = scene_at_index(profile_id, scene_idx)
    sid = str(scene.get("id") or "").strip()

    dance_scenes = {"cantina_dance", "spectacle", "welcome"}
    if sid in dance_scenes:
        if in_cantina:
            out = _post_sidecar_enqueue(action="perform", message="dance", snapshot=snap)
            out["reason"] = f"proactive_scene_{sid}"
            out["incarnation"] = True
            return out
        out = _post_sidecar_enqueue(action="housing_enter", message="cantina", snapshot=snap)
        out["reason"] = f"proactive_scene_{sid}_to_cantina"
        out["incarnation"] = True
        return out

    if sid == "entertainer_progress":
        from lbg_agents.lia_entertainer import suggest_entertainer_action

        phase = str(life_ctx.get("phase") or "learning")
        try:
            mastery = float(life_ctx.get("primary_mastery_pct") or 0)
        except (TypeError, ValueError):
            mastery = 0.0
        try:
            current_tier = int(snap.get("entertainer_tier") or 0)
        except (TypeError, ValueError):
            current_tier = 0
        act = suggest_entertainer_action(
            lifecycle_phase=phase,
            mastery_pct=mastery,
            in_cantina=in_cantina,
            in_training=in_training,
            current_tier=current_tier,
        )
        if act:
            out = _post_sidecar_enqueue(
                action=str(act["action"]),
                message=str(act.get("message") or ""),
                snapshot=snap,
            )
            out["reason"] = "proactive_entertainer_progress"
            out["incarnation"] = True
            return out

    if sid == "artisan_secondary":
        if in_training:
            out = _post_sidecar_enqueue(action="interact", message="examine:trainer", snapshot=snap)
            out["reason"] = "proactive_artisan_trainer"
            out["incarnation"] = True
            return out
        out = _post_sidecar_enqueue(action="housing_enter", message="training", snapshot=snap)
        out["reason"] = "proactive_artisan_training"
        out["incarnation"] = True
        return out

    if sid == "commerce_intro":
        if in_cantina:
            out = _post_sidecar_enqueue(action="interact", message="examine:npc:core3_barman_jax", snapshot=snap)
            out["reason"] = "proactive_commerce_barman"
            out["incarnation"] = True
            return out
        out = _post_sidecar_enqueue(action="housing_enter", message="cantina", snapshot=snap)
        out["reason"] = "proactive_commerce_to_cantina"
        out["incarnation"] = True
        return out

    # social_greet, presence → LLM via build_proactive_prompt
    if proactive_tick_index() % 5 == 0:
        from lbg_agents.core3_quest_autonomy import deterministic_quest_action
        from lbg_agents.core3_player_autonomy import enqueue_direct_action

        quest = deterministic_quest_action(
            get_ai_player("lia"), snapshot=snap, enqueue=enqueue_direct_action
        )
        if quest is not None:
            quest["incarnation"] = True
            return quest
    return None


def build_social_event_prompt(event: dict[str, Any], *, brain: dict[str, Any] | None = None) -> str:
    from lbg_agents.core3_player_events import event_prompt_block

    return (
        f"{event_prompt_block(event)} "
        "Tu es Lia, incarnation de l'orchestrateur : réponds comme un personnage présent, "
        "tutoie Nix et les joueurs IA, donne un ordre concret si on te demande une coordination, "
        "n'evoque jamais tes jauges ou ton etat interne, et ecris sans accents."
    )


def core3_action_player_think(prompt: str, *, enqueue: bool = True) -> dict[str, Any]:
    return {
        "kind": "player_think",
        "player": bot_player_name(),
        "prompt": prompt,
        "enqueue": enqueue,
        "incarnation": True,
    }


def route_context_for_incarnation(
    *,
    prompt: str,
    from_player: str | None = None,
    player_message: str | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "lia_incarnation": True,
        "core3_action": core3_action_player_think(prompt),
    }
    if from_player:
        ctx["lia_from_player"] = from_player.strip()
    if player_message is not None:
        ctx["lia_player_message"] = player_message
    brain = fetch_brain_status()
    if brain:
        ctx["orchestrator_brain"] = brain
    return ctx


def sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "").strip().rstrip("/")


def _sidecar_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_CORE3_IA_TIMEOUT", os.environ.get("LBG_AGENT_DIALOGUE_TIMEOUT", "45")).strip()
    try:
        read_s = max(5.0, float(raw))
    except ValueError:
        read_s = 45.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def fetch_player_snapshot(player: str | None = None) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"online": False, "reason": "sidecar_url_missing"}
    name = (player or bot_player_name()).strip()
    try:
        with httpx.Client(timeout=_sidecar_timeout()) as client:
            resp = client.get(f"{base}/v1/player-snapshot", params={"player": name})
        payload = resp.json() if resp.content else {}
        snap = payload.get("snapshot") if isinstance(payload, dict) else {}
        if not isinstance(snap, dict):
            snap = {}
        if resp.status_code == 409 or not payload.get("ok"):
            snap.setdefault("online", False)
        return snap
    except httpx.HTTPError as exc:
        return {"online": False, "reason": "sidecar_unreachable", "detail": str(exc)}


def _tick_via_sidecar(*, actor_id: str, prompt: str, player: str) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "error": "LBG_CORE3_IA_SIDECAR_URL non défini"}
    body = {"prompt": prompt, "player": player, "enqueue": True, "incarnation": True}
    brain = fetch_brain_status()
    if brain:
        body["orchestrator_brain"] = brain
    with httpx.Client(timeout=_sidecar_timeout()) as client:
        resp = client.post(f"{base}/v1/think", json=body)
    payload = resp.json() if resp.content else {}
    ok = resp.status_code == 200 and bool(payload.get("ok"))
    return {
        "ok": ok,
        "outcome": "ok" if ok else "sidecar_error",
        "http_status": resp.status_code,
        "mode": "sidecar",
        "sidecar": payload,
        "action": payload.get("action"),
        "line": payload.get("line"),
        "incarnation": True,
    }


def _tick_via_orchestrator(*, actor_id: str, prompt: str, player: str) -> dict[str, Any]:
    base = orchestrator_base_url()
    body = {
        "actor_id": actor_id,
        "text": prompt,
        "context": route_context_for_incarnation(prompt=prompt),
    }
    with httpx.Client(timeout=_sidecar_timeout()) as client:
        resp = client.post(f"{base}/v1/route", json=body)
    payload = resp.json() if resp.content else {}
    output = payload.get("output") if isinstance(payload, dict) else {}
    if not isinstance(output, dict):
        output = {}
    ok = resp.status_code == 200 and bool(output.get("ok"))
    return {
        "ok": ok,
        "outcome": "ok" if ok else "route_error",
        "http_status": resp.status_code,
        "mode": "orchestrator",
        "intent": payload.get("intent"),
        "routed_to": payload.get("routed_to"),
        "output": output,
        "action": output.get("action"),
        "line": output.get("line"),
        "incarnation": True,
    }


def incarnate_player_think(
    *,
    prompt: str,
    actor_id: str | None = None,
    via: str | None = None,
) -> dict[str, Any]:
    """Pousse un tour Lia via orchestrateur (invoke) ou sidecar direct."""
    actor = (actor_id or os.environ.get("LBG_CORE3_LIA_ACTOR_ID", "orchestrator:lia")).strip()
    ctx = route_context_for_incarnation(prompt=prompt)
    mode = (via or os.environ.get("LBG_CORE3_LIA_AUTONOMY_MODE", "invoke")).strip().lower()

    if mode == "orchestrator":
        return _tick_via_orchestrator(actor_id=actor, prompt=prompt, player=bot_player_name())

    if mode == "sidecar":
        return _tick_via_sidecar(actor_id=actor, prompt=prompt, player=bot_player_name())

    from lbg_agents.core3_bridge import run_core3_bridge

    out = run_core3_bridge(actor_id=actor, text=prompt, context=ctx)
    out["mode"] = "invoke"
    out["incarnation"] = True
    return out


def hear_player_message(*, from_player: str, text: str) -> dict[str, Any]:
    from lbg_agents.lia_connection import ensure_lia_connected, is_lia_online, lia_auto_connect_enabled

    if lia_auto_connect_enabled() and not is_lia_online():
        conn = ensure_lia_connected()
        if not conn.get("ok"):
            return {
                "ok": False,
                "outcome": "connect_failed",
                "connect": conn,
                "incarnation": True,
            }
    direct = deterministic_hear_action(from_player=from_player, text=text)
    if direct is not None:
        direct["from_player"] = from_player
        direct["heard"] = text
        return direct
    prompt = build_hear_prompt(from_player=from_player, text=text)
    return incarnate_player_think(prompt=prompt, via=os.environ.get("LBG_CORE3_LIA_HEAR_VIA"))


def autonomy_tick() -> dict[str, Any]:
    from lbg_agents.core3_bot_connection import ensure_ia_bots_online
    from lbg_agents.lia_connection import ensure_lia_connected, lia_auto_connect_enabled

    player = bot_player_name()
    snap = fetch_player_snapshot(player)
    if not snap.get("online"):
        if lia_auto_connect_enabled():
            conn = ensure_ia_bots_online()
            lia_conn = (conn.get("bots") or {}).get("lia") or ensure_lia_connected()
            snap = fetch_player_snapshot(player)
            if not snap.get("online") and not lia_conn.get("ok"):
                return {
                    "ok": False,
                    "outcome": "connect_failed",
                    "player": player,
                    "snapshot": snap,
                    "connect": lia_conn,
                    "bots_connect": conn,
                    "incarnation": True,
                }
        else:
            return {
                "ok": True,
                "outcome": "skipped_offline",
                "player": player,
                "snapshot": snap,
                "incarnation": True,
            }
    if not snap.get("online"):
        return {
            "ok": True,
            "outcome": "skipped_offline",
            "player": player,
            "snapshot": snap,
            "incarnation": True,
        }
    from lbg_agents.core3_player_events import (
        commit_inbound_event,
        mark_reactive_handled,
        maybe_apply_social_cooldown,
        peek_latest_inbound_event,
        proactive_suppressed,
    )

    social_event, events_payload = peek_latest_inbound_event("lia", player)
    direct = None
    if social_event is not None and str(social_event.get("type") or "") == "core3.player_spatial_chat":
        direct = deterministic_hear_action(
            from_player=str(social_event.get("actor") or "Gally"),
            text=str(social_event.get("message") or social_event.get("source_line") or ""),
            snapshot=snap,
        )
    if direct is not None:
        prompt = ""
        result = direct
        commit_inbound_event("lia", social_event)
        mark_reactive_handled("lia")
    elif social_event is not None:
        prompt = build_social_event_prompt(social_event)
        result = incarnate_player_think(prompt=prompt)
        commit_inbound_event("lia", social_event)
        mark_reactive_handled("lia")
    elif proactive_suppressed("lia"):
        return {
            "ok": True,
            "outcome": "skipped_proactive_cooldown",
            "player": player,
            "snapshot": snap,
            "social_event": None,
            "events": {
                "ok": bool(events_payload.get("ok")),
                "count": 0,
                "last_event_id": events_payload.get("last_event_id"),
            },
            "incarnation": True,
        }
    else:
        direct = deterministic_proactive_action(snapshot=snap)
        if direct is not None:
            prompt = ""
            result = direct
        else:
            prompt = build_proactive_prompt()
            result = incarnate_player_think(prompt=prompt)
        maybe_apply_social_cooldown("lia", result)
    result["player"] = player
    result["prompt"] = prompt
    result["snapshot"] = snap
    result["social_event"] = social_event
    result["events"] = {
        "ok": bool(events_payload.get("ok")),
        "count": len(events_payload.get("events", [])) if isinstance(events_payload.get("events"), list) else 0,
        "last_event_id": events_payload.get("last_event_id"),
    }
    return result
