"""Élévation agentique : transformer un message Chat actionnable en job autonome.

Inspiré de LBG_Project_03 (`orchestrator/router/agentic.py`). Ici, l'équivalent du graphe
LangGraph de P03 est le **moteur de jobs** (`services/jobs.py`) : au lieu d'un dispatch one-shot,
``/route`` peut créer un job planifié + exécuté en tâche de fond (auto-correction, replan, mémoire).

Désactivé par défaut (``LBG_CHAT_AGENTIC=0``) ; activable globalement ou par requête
(``context.prefer_agentic = true``). N'élève que des intents actionnables connus.
"""

from __future__ import annotations

import os
from typing import Any

from services import jobs as svc_jobs

# Capabilities (= intents) qui bénéficient d'une exécution multi-étapes en arrière-plan.
AGENTIC_INTENTS = frozenset(
    {
        "devops_probe",
        "desktop_control",
        "core3_bot_action",
        "project_pm",
        "world_aid",
    }
)

# Clés de contexte indiquant une **action structurée** explicite (panneaux spécialisés du Pilot).
# Dans ce cas on ne ré-planifie pas depuis le texte : on respecte le dispatch one-shot voulu.
_STRUCTURED_ACTION_KEYS = (
    "devops_action",
    "desktop_action",
    "opengame_action",
    "core3_action",
    "world_action",
    "project_pm",
)


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def chat_agentic_enabled(context: dict[str, Any] | None) -> bool:
    if isinstance(context, dict):
        pref = context.get("prefer_agentic")
        if pref is False:
            return False
        if pref is True:
            return True
    return _truthy(os.environ.get("LBG_CHAT_AGENTIC", "0"))


def should_elevate_to_agentic(intent: str, context: dict[str, Any] | None = None) -> bool:
    """Vrai si la requête doit être déléguée au moteur de jobs plutôt qu'à un dispatch one-shot."""
    if not chat_agentic_enabled(context):
        return False
    if not svc_jobs.runner_enabled():
        # Sans runner de fond, un job resterait « queued » : on garde le dispatch synchrone.
        return False
    if isinstance(context, dict) and any(
        isinstance(context.get(k), dict) or context.get(k) is True for k in _STRUCTURED_ACTION_KEYS
    ):
        # Action structurée explicite (console spécialisée) : pas d'élévation, dispatch one-shot.
        return False
    return intent in AGENTIC_INTENTS


def elevate_to_job(
    *,
    text: str,
    actor_id: str,
    intent: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Crée un job de fond pour ``text`` et renvoie une sortie compatible /route."""
    approval = context.get("devops_approval") or context.get("approval_token")
    approval = approval if isinstance(approval, str) and approval.strip() else None
    job = svc_jobs.create_job(
        actor_id=actor_id,
        objective=text,
        context=context,
        approval_token=approval,
        auto_start=True,
    )
    return {
        "ok": True,
        "agentic": True,
        "elevated_from": intent,
        "job_id": job.id,
        "status": job.status,
        "n_steps": len(job.steps),
        "plan_source": job.plan_source,
        "trace_id": job.trace_id,
        "reply": (
            f"Tâche prise en charge en arrière-plan (job {job.id[:8]}…, {len(job.steps)} étape(s), "
            f"statut « {job.status} »). Suivi dans Pilot ▸ Jobs."
        ),
    }
