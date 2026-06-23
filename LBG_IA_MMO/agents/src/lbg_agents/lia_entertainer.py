"""Progression entertainer Lia — playbook, macros, prochaine action autonome."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_PLAYBOOK_CACHE: dict[str, Any] | None = None


def playbook_path() -> Path:
    raw = os.environ.get("LBG_LIA_ENTERTAINER_PLAYBOOK_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/lia_entertainer_playbook.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "lia_entertainer_playbook.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/lia_entertainer_playbook.json")


def load_playbook() -> dict[str, Any]:
    global _PLAYBOOK_CACHE
    if _PLAYBOOK_CACHE is not None:
        return _PLAYBOOK_CACHE
    path = playbook_path()
    if not path.is_file():
        _PLAYBOOK_CACHE = {}
        return _PLAYBOOK_CACHE
    _PLAYBOOK_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _PLAYBOOK_CACHE


def macro_slots() -> dict[str, dict[str, str]]:
    raw = load_playbook().get("macro_slots")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, row in raw.items():
        if isinstance(row, dict) and row.get("perform"):
            out[str(key)] = {
                "perform": str(row["perform"]),
                "label": str(row.get("label") or ""),
            }
    return out


def skill_tiers() -> list[dict[str, Any]]:
    raw = load_playbook().get("skill_tiers")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def max_skill_tier() -> int:
    tiers = skill_tiers()
    if not tiers:
        return 0
    return max(int(row.get("tier") or 0) for row in tiers)


def dances_for_tier(tier: int) -> list[str]:
    for row in skill_tiers():
        if int(row.get("tier") or -1) == tier:
            raw = row.get("dances_unlocked")
            if isinstance(raw, list):
                return [str(d) for d in raw if str(d).strip()]
    return []


def dances_unlocked_cumulative(tier: int) -> list[str]:
    """Toutes les danses débloquées jusqu'au palier inclus."""
    out: list[str] = []
    seen: set[str] = set()
    for t in range(max(0, int(tier)) + 1):
        for dance in dances_for_tier(t):
            if dance not in seen:
                seen.add(dance)
                out.append(dance)
    return out or ["basic"]


def suggest_entertainer_action(
    *,
    lifecycle_phase: str,
    mastery_pct: float,
    in_cantina: bool,
    in_training: bool,
    current_tier: int = 0,
) -> dict[str, str] | None:
    """Action pending.jsonl suggérée (action + message)."""
    phase = (lifecycle_phase or "learning").strip().lower()
    tier = max(0, int(current_tier))

    if phase in {"learning", "mastery_practice"} and tier < max_skill_tier():
        if in_training:
            return {"action": "learn_entertainer", "message": "trainer"}
        if mastery_pct >= 40 or not in_cantina:
            return {"action": "housing_enter", "message": "training"}
        dances = dances_unlocked_cumulative(tier)
        if dances:
            pick = dances[min(len(dances) - 1, tier % len(dances))]
            return {"action": "perform", "message": f"dance:{pick}"}
        return {"action": "perform", "message": "dance"}

    if in_cantina:
        if tier >= 4:
            return {"action": "entertainer_buff", "message": "audience"}
        dances = dances_unlocked_cumulative(tier)
        if dances:
            pick = dances[tier % len(dances)]
            return {"action": "perform", "message": f"dance:{pick}"}
        return {"action": "perform", "message": "dance"}

    return {"action": "housing_enter", "message": "cantina"}


def macro_hint_for_prompt() -> str:
    slots = macro_slots()
    if not slots:
        return "perform message=dance ou dance:formal pour styles précis."
    parts = [f"{k}={v['perform']}" for k, v in list(slots.items())[:8]]
    return (
        "Macros danseur (barre F) → perform : "
        + ", ".join(parts)
        + ". Visite instructeur : housing_enter training puis learn_entertainer."
    )
