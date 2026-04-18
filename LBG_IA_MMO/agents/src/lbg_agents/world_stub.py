from __future__ import annotations

from typing import Any


def _clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def run_world_stub(*, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Handler déterministe pour produire des commits "monde" sans LLM.

    Contract attendu côté backend (phase 2) :
      - output.commit.flags : dict
      - output.commit.npc_id : optionnel (fallback sur context.world_npc_id)
    """
    ctx = context if isinstance(context, dict) else {}
    npc_id = ctx.get("world_npc_id")
    npc_id = npc_id.strip() if isinstance(npc_id, str) else ""

    action = ctx.get("world_action")
    if not isinstance(action, dict):
        return {
            "agent": "world_stub",
            "handler": "world",
            "error": "world_action manquant (dict attendu dans context)",
        }
    if (action.get("kind") or "").strip() != "aid":
        return {
            "agent": "world_stub",
            "handler": "world",
            "error": "world_action.kind non supporté (attendu: 'aid')",
        }

    def f(name: str) -> float:
        try:
            return float(action.get(name, 0.0))  # type: ignore[arg-type]
        except Exception:
            return 0.0

    def i(name: str) -> int:
        try:
            return int(action.get(name, 0))  # type: ignore[arg-type]
        except Exception:
            return 0

    # Deltas bornés (alignés sur backend + serveur WS).
    hunger_delta = _clamp(f("hunger_delta"), -1.0, 1.0)
    thirst_delta = _clamp(f("thirst_delta"), -1.0, 1.0)
    fatigue_delta = _clamp(f("fatigue_delta"), -1.0, 1.0)
    rep_delta = max(-100, min(100, i("reputation_delta")))

    flags: dict[str, Any] = {
        "aid_hunger_delta": hunger_delta,
        "aid_thirst_delta": thirst_delta,
        "aid_fatigue_delta": fatigue_delta,
        "aid_reputation_delta": rep_delta,
    }
    # Éviter un commit “vide” (noop) côté jeu.
    if hunger_delta == 0.0 and thirst_delta == 0.0 and fatigue_delta == 0.0 and rep_delta == 0:
        return {
            "agent": "world_stub",
            "handler": "world",
            "note": "noop (deltas tous à 0)",
            "commit": {"npc_id": npc_id or None, "flags": {}},
        }

    return {
        "agent": "world_stub",
        "handler": "world",
        "commit": {"npc_id": npc_id or None, "flags": flags},
        "remote": {
            "reply": "Action monde: aide appliquée (commit).",
            "meta": {"kind": "world_aid", "npc_id": npc_id or None},
        },
    }

