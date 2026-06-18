"""Agent Chroniqueur — objectifs faction/roster depuis faction_goals.json (v1 dry-run)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from lbg_agents.core3_economy_loop import load_economy_config
from lbg_agents.economy_director import collect_shop_signals


def faction_goals_path() -> Path:
    raw = os.environ.get("LBG_FACTION_GOALS_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/faction_goals.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "faction_goals.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/faction_goals.json")


def load_faction_goals() -> dict[str, Any]:
    path = faction_goals_path()
    if not path.is_file():
        return {"schema_version": 1, "factions": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"schema_version": 1, "factions": []}


def _stock_for_shop_item(
    signals: list[dict[str, Any]],
    shop_id: str,
    item_template: str | None,
) -> int | None:
    for sig in signals:
        if str(sig.get("shop_id") or "") != shop_id:
            continue
        if item_template and str(sig.get("item_template") or "") != item_template:
            continue
        try:
            return int(sig.get("stock") or 0)
        except (TypeError, ValueError):
            return 0
    return None


def evaluate_world_state(
    *,
    economy: dict[str, Any] | None = None,
    stock_overrides: dict[str, int] | None = None,
    goals_doc: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retourne les objectifs de faction actifs selon l'état des shops."""
    doc = goals_doc if isinstance(goals_doc, dict) else load_faction_goals()
    factions = doc.get("factions")
    if not isinstance(factions, list):
        return []

    signals = collect_shop_signals(economy, stock_overrides=stock_overrides)
    active: list[dict[str, Any]] = []

    for faction in factions:
        if not isinstance(faction, dict):
            continue
        faction_id = str(faction.get("faction_id") or "").strip()
        goals = faction.get("goals")
        if not isinstance(goals, list):
            continue
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            condition = str(goal.get("condition") or "").strip()
            shop_id = str(goal.get("shop_id") or "").strip()
            template = str(goal.get("item_template") or "").strip() or None
            try:
                threshold = int(goal.get("threshold") or 10)
            except (TypeError, ValueError):
                threshold = 10

            triggered = False
            stock: int | None = None
            if condition == "shop_stock_below":
                stock = _stock_for_shop_item(signals, shop_id, template)
                if stock is not None and stock < threshold:
                    triggered = True

            if triggered:
                active.append(
                    {
                        "faction_id": faction_id,
                        "goal_id": str(goal.get("goal_id") or ""),
                        "priority": int(goal.get("priority") or 99),
                        "condition": condition,
                        "shop_id": shop_id,
                        "stock": stock,
                        "threshold": threshold,
                        "roster_id": str(goal.get("roster_id") or ""),
                        "scene_profile": str(goal.get("scene_profile") or ""),
                        "hint_action": str(goal.get("hint_action") or "npc_scene"),
                    }
                )

    active.sort(key=lambda row: (int(row.get("priority") or 99), str(row.get("faction_id"))))
    return active


def enqueue_roster_hints(
    goals: list[dict[str, Any]],
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Produit des hints roster (v1 : structures JSON ; écriture pending.jsonl hors scope dry-run)."""
    hints: list[dict[str, Any]] = []
    for goal in goals:
        roster_id = str(goal.get("roster_id") or "").strip()
        if not roster_id:
            continue
        hints.append(
            {
                "kind": "roster_hint",
                "roster_id": roster_id,
                "scene_profile": goal.get("scene_profile"),
                "hint_action": goal.get("hint_action"),
                "faction_id": goal.get("faction_id"),
                "goal_id": goal.get("goal_id"),
                "dry_run": dry_run,
                "note": "Enqueue sidecar / pending.jsonl via capability world_direct (phase 5.3)",
            }
        )
    return hints


def run_chronicler_tick(
    *,
    dry_run: bool = True,
    economy: dict[str, Any] | None = None,
    stock_overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    active = evaluate_world_state(economy=economy, stock_overrides=stock_overrides)
    hints = enqueue_roster_hints(active, dry_run=dry_run)
    return {
        "ok": True,
        "agent": "world_chronicler",
        "dry_run": dry_run,
        "ts": int(time.time()),
        "active_goals": active,
        "roster_hints": hints,
        "active_goal_count": len(active),
    }
