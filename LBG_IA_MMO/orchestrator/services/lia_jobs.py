"""Helpers planification jobs Cowork / proactive — incarnation Lia en MMO."""

from __future__ import annotations

import re
from typing import Any

LIA_PLAYER = "Lia"
LIA_PLAYER_ID = "lia"
LIA_ACTOR_ID = "orchestrator:lia"

_LIA_MMO_INTENT_RE = re.compile(
    r"\b(jouer|joue|incarn|tick|mmo|core3|tatooine|en jeu|bot|pilote|piloter|"
    r"fais|faire|tour|autonom|observe|salue|parle|coordonne|prime|sidecar|"
    r"joueur ia|incarnation|pense|agis|action en jeu)\b",
    re.IGNORECASE,
)


def objective_mentions_lia_mmo(normalized: str) -> bool:
    """Objectif explicite de pilotage Lia / MMO."""
    if not re.search(r"\blia\b", normalized, re.IGNORECASE):
        return False
    return bool(_LIA_MMO_INTENT_RE.search(normalized))


def lia_tick_prompt_from_objective(objective: str) -> str:
    raw = (objective or "").strip()
    if raw and objective_mentions_lia_mmo(raw.lower()):
        return raw[:2000]
    return (
        "Tu es Lia, incarnation de l'orchestrateur LBG en jeu. "
        "Observe ta zone, interagis si pertinent, reste coherente avec ton role."
    )


def lia_core3_context_patch(*, prompt: str) -> dict[str, Any]:
    action: dict[str, Any] = {
        "kind": "player_think",
        "player": LIA_PLAYER,
        "prompt": prompt,
        "enqueue": True,
        "incarnation": True,
    }
    return {
        "lia_incarnation": True,
        "core3_action": action,
        "core3_player_id": LIA_PLAYER_ID,
        "core3_autonomy": True,
    }


def lia_core3_plan_action(*, prompt: str) -> dict[str, Any]:
    return dict(lia_core3_context_patch(prompt=prompt)["core3_action"])
