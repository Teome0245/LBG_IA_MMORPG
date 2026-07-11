"""Phase D — think/tick joueurs IA via équipe (L2 + approbation)."""

from __future__ import annotations

import os

from team.models import TeamTask


def think_enabled() -> bool:
    return os.environ.get("LBG_TEAM_PLAYER_IA_THINK_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def think_requires_approval() -> bool:
    return os.environ.get("LBG_TEAM_PLAYER_IA_THINK_REQUIRES_APPROVAL", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def resolve_player_ia_mode(task: TeamTask) -> str:
    raw = task.context.get("player_ia_mode") or task.context.get("player_ia_action")
    if isinstance(raw, str):
        mode = raw.strip().lower()
        if mode in ("think", "think_tick", "autonomy_tick", "tick"):
            return "think_tick"
    text = (task.objective or "").lower()
    if any(k in text for k in ("think", "tick", "autonomie", "tour lia", "tour nix", "incarne")):
        return "think_tick"
    return "probe"


def resolve_player_id(task: TeamTask) -> str:
    for key in ("player_id", "core3_player_id", "player"):
        val = task.context.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    obj = (task.objective or "").lower()
    for name in ("lia", "nix", "mira", "kael"):
        if name in obj:
            return name
    return os.environ.get("LBG_TEAM_PLAYER_IA_THINK_DEFAULT_PLAYER", "lia").strip().lower() or "lia"


def should_require_approval_for_task(task: TeamTask) -> bool:
    if resolve_player_ia_mode(task) != "think_tick":
        return False
    if task.context.get("player_ia_dry_run") is True:
        return False
    return think_requires_approval()


def infer_approval_on_create(role: str, objective: str, context: dict[str, object]) -> bool | None:
    if role != "player_ia":
        return None
    task = TeamTask(
        id="pending",
        role="player_ia",
        objective=objective,
        status="queued",
        priority="normal",
        approval_required=False,
        actor_id="",
        context=dict(context),
    )
    if resolve_player_ia_mode(task) != "think_tick":
        return None
    return True if think_requires_approval() else False


def execute_player_ia_think(task: TeamTask) -> dict[str, object]:
    if not think_enabled():
        return {
            "kind": "player_ia_think",
            "ok": False,
            "error": "LBG_TEAM_PLAYER_IA_THINK_ENABLED=0",
        }
    player_id = resolve_player_id(task)
    via = str(task.context.get("player_ia_via") or "team").strip() or "team"
    from lbg_agents.core3_player_autonomy import player_autonomy_tick

    out = player_autonomy_tick(player_id, via=via)
    outcome = str(out.get("outcome") or "")
    ok = bool(out.get("ok", True)) and outcome not in ("error", "failed")
    return {
        "kind": "player_ia_think",
        "ok": ok,
        "player_id": player_id,
        "via": via,
        "outcome": outcome or None,
        "output": out,
    }
