"""Quêtes joueurs IA — progression_goals → core3_quest_templates.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lbg_agents.core3_players import Core3IaPlayer

GOAL_TO_QUEST: dict[str, str] = {
    "forage_economy": "quest:mos_gather_bar_fruit",
    "commerce_bazaar": "quest:mos_gather_bar_spice",
    "scout_skills": "quest:mos_investigate_noise",
    "marksman_novice": "quest:mos_investigate_noise",
    "entertainer_master": "quest:mos_delivery_water",
    "artisan_novice": "quest:mos_repair_generator",
    "craft_demo": "quest:mos_repair_generator",
    "brawler_novice": "quest:mos_repair_generator",
    "medic_novice": "quest:mos_investigate_noise",
    "entertainer_novice": "quest:mos_delivery_water",
    "train_players": "quest:mos_investigate_noise",
    "rep:cantina_bar": "quest:mos_gather_bar_fruit",
}


def quest_templates_path() -> Path:
    raw = os.environ.get("LBG_CORE3_QUEST_TEMPLATES_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_quest_templates.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_quest_templates.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_quest_templates.json")


def quest_state_path() -> Path:
    raw = os.environ.get("LBG_CORE3_QUEST_STATE_JSONL", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/quest_state.jsonl"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "ia_bridge" / "quest_state.jsonl",
    ):
        if candidate.parent.is_dir() or not candidate.is_absolute():
            return candidate
    return Path("content/core3/ia_bridge/quest_state.jsonl")


def load_quest_templates() -> list[dict[str, Any]]:
    path = quest_templates_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("templates") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def template_by_id(quest_id: str) -> dict[str, Any] | None:
    wanted = quest_id.strip()
    for row in load_quest_templates():
        if str(row.get("id") or "").strip() == wanted:
            return row
    return None


def pick_quest_for_player(player: Core3IaPlayer) -> str | None:
    goals = list(player.progression_goals) or ["forage_economy"]
    idx = 0
    if player.id:
        idx = sum(ord(c) for c in player.id) % len(goals)
    for offset in range(len(goals)):
        goal = goals[(idx + offset) % len(goals)]
        qid = GOAL_TO_QUEST.get(goal.strip().lower())
        if qid and template_by_id(qid):
            return qid
    templates = load_quest_templates()
    if templates:
        return str(templates[0].get("id") or "").strip() or None
    return None


def _read_quest_events() -> list[dict[str, Any]]:
    # 1. Tentative d'interrogation du sidecar via HTTP
    try:
        from lbg_agents.core3_player_autonomy import sidecar_base_url, _timeout
        import httpx
        base = sidecar_base_url()
        if base:
            with httpx.Client(timeout=_timeout()) as client:
                resp = client.get(f"{base}/v1/quest-state")
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, dict) and "quest_states" in payload:
                    states = payload["quest_states"]
                    if isinstance(states, list):
                        return states
    except Exception:
        pass

    # 2. Fallback sur le fichier local
    path = quest_state_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
    except (OSError, json.JSONDecodeError):
        return []
    return out


def active_quest_id(player_firstname: str) -> str | None:
    name = player_firstname.strip()
    if not name:
        return None
    accepted: set[str] = set()
    turned: set[str] = set()
    for row in _read_quest_events():
        if str(row.get("player") or "").strip() != name:
            continue
        qid = str(row.get("quest_id") or "").strip()
        if not qid:
            continue
        ev = str(row.get("type") or "").strip().lower()
        if ev == "accept":
            accepted.add(qid)
        elif ev == "turnin":
            turned.add(qid)
    for qid in accepted:
        if qid not in turned:
            return qid
    return None


def quest_prompt_block(player: Core3IaPlayer) -> str:
    active = active_quest_id(player.firstname)
    if active:
        tpl = template_by_id(active)
        title = str(tpl.get("title") or active) if tpl else active
        return f"Quete active: {title} ({active}). Priorite: terminer ou quest_turnin."
    nxt = pick_quest_for_player(player)
    if nxt:
        tpl = template_by_id(nxt)
        title = str(tpl.get("title") or nxt) if tpl else nxt
        return f"Quete suggeree (progression_goals): {title} ({nxt})."
    return ""


def deterministic_quest_action(
    player: Core3IaPlayer,
    *,
    snapshot: dict[str, Any] | None,
    enqueue,
) -> dict[str, Any] | None:
    """Accepte / avance / rend une quete sans LLM."""
    snap = snapshot if isinstance(snapshot, dict) else {}
    active = active_quest_id(player.firstname)
    if active:
        tpl = template_by_id(active) or {}
        qtype = str(tpl.get("type") or "").strip().lower()
        if qtype == "repair":
            coords = tpl.get("check_coords") if isinstance(tpl.get("check_coords"), dict) else {}
            tx = float(coords.get("x") or 3520)
            ty = float(coords.get("y") or -4788)
            tz = float(coords.get("z") or 5)
            px = float(snap.get("x") or 0)
            py = float(snap.get("y") or 0)
            dist = ((px - tx) ** 2 + (py - ty) ** 2) ** 0.5
            if dist > float(coords.get("radius_m") or 12):
                out = enqueue(
                    player,
                    action="move_to",
                    message="quest_repair_site",
                    snapshot=snap,
                    target_xyz=(tx, ty, tz),
                )
                out["reason"] = "quest_repair_travel"
                return out
        elif qtype == "gather":
            target_count = int(tpl.get("target_count") or 1)
            inv_count = int(snap.get("inventory_count") or 0)
            if inv_count < target_count:
                in_int = snap.get("in_interior")
                in_interior = in_int in {True, 1, "1", "true", "True"}
                if in_interior:
                    out = enqueue(
                        player,
                        action="move_to",
                        message="mos_eisley_outdoor",
                        snapshot=snap,
                        target_xyz=(3520.0, -4810.0, 5.0),
                    )
                    out["reason"] = "quest_gather_exit_interior"
                    return out
                out = enqueue(player, action="perform", message="forage", snapshot=snap)
                out["reason"] = "quest_gather_forage"
                return out
        out = enqueue(
            player,
            action="interact",
            message=f"quest_turnin:{player.firstname}:{active}",
            snapshot=snap,
        )
        out["reason"] = "quest_turnin"
        return out

    quest_id = pick_quest_for_player(player)
    if not quest_id:
        return None
    giver = str((template_by_id(quest_id) or {}).get("giver_pilot_id") or "npc:core3_vex_sorn")
    enqueue(
        player,
        action="offer_quest",
        message=f"{player.firstname}|{quest_id}",
        snapshot=snap,
        enqueue_player=giver,
    )
    out = enqueue(
        player,
        action="interact",
        message=f"quest_accept:{player.firstname}:{quest_id}",
        snapshot=snap,
    )
    out["reason"] = "quest_accept"
    return out
