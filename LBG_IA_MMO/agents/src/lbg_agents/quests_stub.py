"""
Logique locale « quêtes » (stub) — appelée par `dispatch` et par `quests_http_app`.

Ne doit **pas** lire `LBG_AGENT_QUESTS_URL` (évite récursion HTTP quand le service
et l’orchestrator partagent le même fichier d’environnement).
"""

from __future__ import annotations

import re
import time
from typing import Any


def run_quests_stub(*, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    t = (text or "").strip()
    npc = context.get("npc_name") if isinstance(context, dict) else None
    giver = npc.strip() if isinstance(npc, str) and npc.strip() else "Un habitant"
    npc_id = context.get("world_npc_id") if isinstance(context, dict) else None
    npc_id = npc_id.strip() if isinstance(npc_id, str) and npc_id.strip() else None

    quest_state = context.get("quest_state") if isinstance(context, dict) else None
    quest_id = None
    status = "open"
    step = 0
    if isinstance(quest_state, dict):
        qid = quest_state.get("quest_id")
        if isinstance(qid, str) and qid.strip():
            quest_id = qid.strip()
        st = quest_state.get("status")
        if isinstance(st, str) and st.strip():
            status = st.strip()
        raw_step = quest_state.get("step")
        if isinstance(raw_step, int) and raw_step >= 0:
            step = raw_step

    if quest_id:
        if status == "completed":
            updated_state = {"quest_id": quest_id, "status": "completed", "step": step}
            return {
                "agent": "quests_stub",
                "handler": "quests",
                "actor_id": actor_id,
                "request_text": t,
                "quest_state": updated_state,
                "meta": {"stub": True},
            }

        # Phase 2 : proposer un commit monde lorsque le joueur "accepte" explicitement une quête.
        # Le backend appliquera ce commit vers mmmorpg si configuré (commit_result dans /pilot/route).
        low = t.lower()
        if status == "open" and step == 0 and re.search(r"\b(accepte|j'accepte|j accepte|accept)\b", low):
            updated_state = {"quest_id": quest_id, "status": "accepted", "step": step}
            out: dict[str, Any] = {
                "agent": "quests_stub",
                "handler": "quests",
                "actor_id": actor_id,
                "request_text": t,
                "quest_state": updated_state,
                "meta": {"stub": True},
            }
            if npc_id:
                out["commit"] = {"npc_id": npc_id, "flags": {"quest_accepted": True, "quest_id": quest_id}}
            return out

        new_step = step + 1
        new_status = "completed" if new_step >= 2 else status
        updated_state = {"quest_id": quest_id, "status": new_status, "step": new_step}
        return {
            "agent": "quests_stub",
            "handler": "quests",
            "actor_id": actor_id,
            "request_text": t,
            "quest_state": updated_state,
            "meta": {"stub": True},
        }

    low = t.lower()
    if re.search(r"\b(loup|loups|wolf)\b", low):
        theme = "loups"
        objective = "Éliminer 3 loups aux abords du chemin."
        reward = {"gold": 12, "xp": 80, "items": ["Peau de loup (x1)"]}
    elif re.search(r"\b(bandit|bandits|brigand)\b", low):
        theme = "bandits"
        objective = "Repousser les bandits près du vieux pont."
        reward = {"gold": 18, "xp": 110, "items": ["Dague émoussée (x1)"]}
    elif re.search(r"\b(herbe|plante|plantes|cueillir|cueillette)\b", low):
        theme = "cueillette"
        objective = "Rapporter 5 herbes médicinales."
        reward = {"gold": 8, "xp": 60, "items": ["Potion mineure (x1)"]}
    else:
        theme = "aide"
        objective = "Aider un villageois avec une tâche simple."
        reward = {"gold": 10, "xp": 70, "items": []}

    title = f"Petite quête : {theme}"
    quest = {
        "title": title,
        "giver": giver,
        "objectives": [{"kind": "task", "text": objective, "status": "open"}],
        "rewards": reward,
        "next_steps": [
            "Accepter la quête.",
            "Accomplir l’objectif.",
            "Revenir voir le donneur de quête.",
        ],
    }
    quest_id = f"q-{int(time.time())}-{abs(hash(actor_id)) % 10_000}"
    qstate = {"quest_id": quest_id, "status": "open", "step": 0}
    return {
        "agent": "quests_stub",
        "handler": "quests",
        "actor_id": actor_id,
        "request_text": t,
        "quest": quest,
        "quest_state": qstate,
        "meta": {"stub": True},
    }
