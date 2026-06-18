"""Tests des briques cognitives du moteur de jobs (rapatriées de P03) :
validation sémantique (succès trompeur), replan automatique borné, mémoire d'expériences.
"""

import os

os.environ.setdefault("LBG_JOBS_RUNNER_ENABLED", "0")
os.environ["LBG_JOBS_STATE_PATH"] = ""  # persistance disque désactivée

import pytest  # noqa: E402

from services import jobs as svc_jobs  # noqa: E402
from services import planner as svc_planner  # noqa: E402
from services import experience_memory as svc_memory  # noqa: E402


def _reset_dispatch() -> None:
    svc_jobs._dispatch = svc_jobs.invoke_after_route


# --------------------------------------------------------------------------- #
# 1. Validation sémantique : un "ok" en trompe-l'œil est traité comme un échec
# --------------------------------------------------------------------------- #


def test_misleading_success_is_treated_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_JOBS_MAX_REPLANS", "0")  # isole la validation sémantique
    monkeypatch.setenv("LBG_JOBS_STEP_MAX_ATTEMPTS", "1")

    def misleading(routed_to, *, actor_id, text, context):  # noqa: ANN001
        # Techniquement ok=True mais l'outcome dit "bad_request" -> hors-sujet.
        return {"ok": True, "outcome": "bad_request"}

    svc_jobs._dispatch = misleading
    try:
        job = svc_jobs.create_job(
            actor_id="ops:sem",
            objective="ouvrir une app",
            steps=[
                {
                    "capability": "desktop_control",
                    "routed_to": "agent.desktop",
                    "action_context_key": "desktop_action",
                    "action": {"kind": "open_app", "app": "vghd"},
                    "context_patch": {
                        "desktop_action": {"kind": "open_app", "app": "vghd"},
                        "desktop_dry_run": True,
                    },
                    "summary": "ouvrir vghd",
                    "risk_level": "high",
                }
            ],
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "failed"
        assert "trompeur" in (final.steps[0].error or "").lower()
    finally:
        _reset_dispatch()


# --------------------------------------------------------------------------- #
# 2. Replan automatique : une étape qui échoue déclenche une re-planification
# --------------------------------------------------------------------------- #


def test_auto_replan_recovers_with_new_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_JOBS_MAX_REPLANS", "1")
    monkeypatch.setenv("LBG_JOBS_STEP_MAX_ATTEMPTS", "1")

    calls = {"n": 0}

    def fake_plan(objective, context=None, *, error_log=None, memories=None):  # noqa: ANN001
        calls["n"] += 1
        text = "try-1" if calls["n"] == 1 else "try-2"
        # Au replan, on vérifie que le journal d'erreurs est bien transmis.
        if calls["n"] >= 2:
            assert error_log and error_log[-1].get("error")
        return svc_planner.PlanResult(
            steps=[
                svc_planner.PlanStep(
                    capability="npc_dialogue",
                    routed_to="agent.dialogue",
                    summary="étape",
                    risk_level="low",
                    text=text,
                )
            ],
            source="deterministic",
        )

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        if "try-1" in text:
            return {"ok": False, "error": "boom"}
        return {"ok": True, "agent": "fake"}

    monkeypatch.setattr(svc_planner, "plan_objective", fake_plan)
    svc_jobs._dispatch = fake_dispatch
    try:
        job = svc_jobs.create_job(actor_id="ops:replan", objective="objectif replan", auto_start=True)
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "done"
        assert final.replans == 1
        assert any(e.get("kind") == "replanned" for e in final.events)
    finally:
        _reset_dispatch()


def test_no_replan_when_plan_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replan sauté si le nouveau plan est identique (évite la boucle stérile)."""
    monkeypatch.setenv("LBG_JOBS_MAX_REPLANS", "2")
    monkeypatch.setenv("LBG_JOBS_STEP_MAX_ATTEMPTS", "1")

    def fake_plan(objective, context=None, *, error_log=None, memories=None):  # noqa: ANN001
        return svc_planner.PlanResult(
            steps=[
                svc_planner.PlanStep(
                    capability="npc_dialogue",
                    routed_to="agent.dialogue",
                    summary="étape",
                    risk_level="low",
                    text="toujours pareil",
                )
            ],
            source="deterministic",
        )

    monkeypatch.setattr(svc_planner, "plan_objective", fake_plan)
    svc_jobs._dispatch = lambda *a, **k: {"ok": False, "error": "boom"}
    try:
        job = svc_jobs.create_job(actor_id="ops:noreplan", objective="objectif stable", auto_start=True)
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "failed"
        assert final.replans == 0
        assert any(e.get("kind") == "replan_skipped" for e in final.events)
    finally:
        _reset_dispatch()


# --------------------------------------------------------------------------- #
# 3. Mémoire d'expériences : enregistrement + rappel par similarité
# --------------------------------------------------------------------------- #


def test_experience_record_and_recall(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    svc_memory.reset_for_tests()
    monkeypatch.setenv("LBG_JOBS_MEMORY_ENABLED", "1")
    monkeypatch.setenv("LBG_JOBS_MEMORY_PATH", str(tmp_path / "experiences.jsonl"))

    svc_memory.record_experience(
        "redémarrer le service backend nginx",
        outcome="success",
        resolution="restart via devops",
        tags=["success"],
    )
    svc_memory.record_experience(
        "ouvrir le jeu vghd sur le pc",
        outcome="failed",
        problem="allowlist worker",
        tags=["failed"],
    )

    hits = svc_memory.recall_similar("redémarrer backend nginx maintenant", k=2)
    assert hits
    assert "backend" in hits[0]["goal"]

    # Persistance disque : rechargement depuis le JSONL.
    svc_memory.reset_for_tests()
    again = svc_memory.recall_similar("ouvrir vghd jeu", k=2)
    assert any("vghd" in h["goal"] for h in again)


def test_completed_job_records_experience(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    svc_memory.reset_for_tests()
    monkeypatch.setenv("LBG_JOBS_MEMORY_ENABLED", "1")
    monkeypatch.setenv("LBG_JOBS_MEMORY_PATH", str(tmp_path / "exp.jsonl"))
    svc_jobs._dispatch = lambda *a, **k: {"ok": True, "agent": "fake"}
    try:
        job = svc_jobs.create_job(actor_id="ops:mem", objective="objectif mémoire test", auto_start=True)
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None and final.status == "done"
        hits = svc_memory.recall_similar("objectif mémoire test", k=3)
        assert any(h.get("outcome") == "done" for h in hits)
    finally:
        _reset_dispatch()
