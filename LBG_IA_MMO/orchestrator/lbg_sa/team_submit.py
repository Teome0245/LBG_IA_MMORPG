"""Soumission de tâches Team pour le kickoff LBG Studios Agents phase 0."""

from __future__ import annotations

from team import store as team_store

KICKOFF_BATCH = "phase0"
_KICKOFF_CTX_KEY = "lbg_sa_kickoff_batch"
_LEGACY_KICKOFF_CTX_KEY = "fable5_kickoff_batch"


def _kickoff_objectives() -> list[dict[str, object]]:
    return [
        {
            "role": "pm",
            "objective": (
                "LBG_SA phase0 — valider studios Cortex/Corps/Peau, "
                "prioriser vertical slice joueur IA + mémoire namespacée"
            ),
            "priority": "high",
            "context": {
                "subproject": "lbg_sa",
                _KICKOFF_CTX_KEY: KICKOFF_BATCH,
                "lbg_sa_track": "pm_validation",
            },
        },
        {
            "role": "qa",
            "objective": (
                "LBG_SA phase0 — smoke : tests orchestrator/tests/test_lbg_sa_* "
                "et lbg_sa_memory après run admin_infra Atlas"
            ),
            "priority": "normal",
            "context": {
                "subproject": "lbg_sa",
                _KICKOFF_CTX_KEY: KICKOFF_BATCH,
                "lbg_sa_track": "qa_smoke",
            },
        },
        {
            "role": "admin_infra",
            "objective": (
                "LBG_SA phase0 — poursuivre local LLM lab ; vérifier learnings team/atlas "
                "après watchdog bench"
            ),
            "priority": "normal",
            "context": {
                "subproject": "lbg_sa",
                _KICKOFF_CTX_KEY: KICKOFF_BATCH,
                "lbg_sa_track": "atlas_memory",
                "admin_infra_focus": True,
            },
        },
    ]


def kickoff_already_queued(*, batch: str = KICKOFF_BATCH) -> bool:
    if not team_store.team_enabled():
        return False
    for task in team_store.list_tasks(limit=200):
        ctx = task.context if isinstance(task.context, dict) else {}
        if task.status not in ("queued", "running", "done"):
            continue
        if ctx.get(_KICKOFF_CTX_KEY) == batch or ctx.get(_LEGACY_KICKOFF_CTX_KEY) == batch:
            return True
    return False


def enqueue_lbg_sa_kickoff_tasks(
    *,
    actor_id: str = "system:lbg_sa",
    force: bool = False,
    batch: str = KICKOFF_BATCH,
) -> dict[str, object]:
    """Enfile les tâches kickoff ; idempotent sauf force=True."""
    if not team_store.team_enabled():
        return {"ok": False, "error": "LBG_TEAM_ENABLED=0", "tasks": []}
    if not force and kickoff_already_queued(batch=batch):
        return {"ok": True, "skipped": "kickoff_batch_exists", "batch": batch, "tasks": []}

    created: list[dict[str, object]] = []
    for spec in _kickoff_objectives():
        ctx = dict(spec.get("context") or {})
        if batch != KICKOFF_BATCH:
            ctx[_KICKOFF_CTX_KEY] = batch
        task = team_store.create_task(
            role=str(spec["role"]),
            objective=str(spec["objective"]),
            actor_id=actor_id,
            priority=str(spec.get("priority") or "normal"),
            approval_required=False,
            context=ctx,
        )
        created.append({"id": task.id, "role": task.role, "status": task.status, "objective": task.objective})
    return {"ok": True, "skipped": None, "batch": batch, "tasks": created}
