"""
Combat (stub local) — sans effet sur `mmo_server` ni persistance monde.

Appelé par `dispatch` et par `combat_http_app`. Ne lit pas `LBG_AGENT_COMBAT_URL`.

Si `context.encounter_state` contient un `encounter_id` valide et un statut non terminal,
le stub poursuit la rencontre (tour suivant, PV simplifiés). Sinon, nouvelle rencontre.
"""

from __future__ import annotations

import re
import time
from typing import Any


def _resolve_target(text: str, context: dict[str, Any]) -> str:
    t = (text or "").strip()
    low = t.lower()
    target: str | None = None
    for key in ("enemy_name", "target_name", "opponent"):
        v = context.get(key)
        if isinstance(v, str) and v.strip():
            target = v.strip()
            break
    if not target:
        if re.search(r"\bgobelin\b", low):
            target = "Gobelin"
        elif re.search(r"\bloup\b", low):
            target = "Loup"
        elif re.search(r"\bbandit\b", low):
            target = "Bandit"
        else:
            target = "Adversaire"
    return target


def _hp_pair(hp: Any) -> tuple[int, int]:
    if not isinstance(hp, dict):
        return 100, 100
    p_raw, o_raw = hp.get("player"), hp.get("opponent")
    pi = int(p_raw) if isinstance(p_raw, (int, float)) else 100
    oi = int(o_raw) if isinstance(o_raw, (int, float)) else 100
    return max(0, pi), max(0, oi)


def _compact_encounter(encounter: dict[str, Any]) -> dict[str, Any]:
    es: dict[str, Any] = {
        "encounter_id": encounter["encounter_id"],
        "round": encounter["round"],
        "opponent": encounter["opponent"],
        "hp": encounter["hp"],
    }
    st = encounter.get("status")
    if isinstance(st, str) and st.strip():
        es["status"] = st.strip()
    return es


def _payload(actor_id: str, text: str, encounter: dict[str, Any]) -> dict[str, Any]:
    t = (text or "").strip()
    return {
        "agent": "combat_stub",
        "handler": "combat",
        "actor_id": actor_id,
        "request_text": t,
        "encounter": encounter,
        "encounter_state": _compact_encounter(encounter),
        "meta": {"stub": True, "sterile": True},
    }


def _try_continue(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
    encounter_state: dict[str, Any],
    fallback_opponent: str,
) -> dict[str, Any] | None:
    eid_raw = encounter_state.get("encounter_id")
    if not isinstance(eid_raw, str) or not eid_raw.strip():
        return None
    eid = eid_raw.strip()

    prev_status = encounter_state.get("status")
    if isinstance(prev_status, str) and prev_status.strip().lower() in ("victory", "defeat", "fled"):
        return None

    rnd_raw = encounter_state.get("round")
    rnd = int(rnd_raw) if isinstance(rnd_raw, (int, float)) else 1
    rnd = max(1, rnd)

    opp_raw = encounter_state.get("opponent")
    opp = opp_raw.strip() if isinstance(opp_raw, str) and opp_raw.strip() else fallback_opponent

    php, ohp = _hp_pair(encounter_state.get("hp"))
    low = (text or "").lower()

    if re.search(r"\b(fuir|fuite)\b", low):
        encounter = {
            "encounter_id": eid,
            "opponent": opp,
            "round": rnd + 1,
            "hp": {"player": php, "opponent": ohp},
            "suggested_actions": ["Attaquer", "Se défendre", "Fuir"],
            "narrative": f"Vous prenez le large face à {opp}.",
            "status": "fled",
        }
        return _payload(actor_id, text, encounter)

    defend = bool(re.search(r"\b(défendre|defend|se défendre)\b", low))
    ply_dmg = 12
    opp_dmg = 3 if defend else 8

    ohp = max(0, ohp - ply_dmg)
    if ohp > 0:
        php = max(0, php - opp_dmg)

    new_round = rnd + 1
    if ohp <= 0:
        status = "victory"
        narr = f"{opp} tombe à terre. Victoire !"
    elif php <= 0:
        status = "defeat"
        narr = "Vous êtes hors combat."
    else:
        status = "ongoing"
        narr = f"Tour {new_round} : échanges de coups avec {opp}."

    encounter = {
        "encounter_id": eid,
        "opponent": opp,
        "round": new_round,
        "hp": {"player": php, "opponent": ohp},
        "suggested_actions": ["Attaquer", "Se défendre", "Fuir"],
        "narrative": narr,
        "status": status,
    }
    return _payload(actor_id, text, encounter)


def run_combat_stub(*, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    target = _resolve_target(text, ctx)

    es = ctx.get("encounter_state")
    if isinstance(es, dict):
        continued = _try_continue(
            actor_id=actor_id,
            text=text,
            context=ctx,
            encounter_state=es,
            fallback_opponent=target,
        )
        if continued is not None:
            return continued

    encounter_id = f"c-{int(time.time())}-{abs(hash(actor_id)) % 10_000}"
    encounter = {
        "encounter_id": encounter_id,
        "opponent": target,
        "round": 1,
        "hp": {"player": 100, "opponent": 100},
        "suggested_actions": ["Attaquer", "Se défendre", "Fuir"],
        "narrative": f"Un affrontement commence contre {target}.",
        "status": "ongoing",
    }
    return _payload(actor_id, text, encounter)
