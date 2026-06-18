"""
Tests du moteur de jobs autonome ("type Cowork", sous garde-fous).

On désactive le runner de fond et la persistance disque pour rester déterministe,
et on pilote le moteur étape par étape (``advance_job`` / ``run_job_to_completion``).
"""

import os

os.environ.setdefault("LBG_JOBS_RUNNER_ENABLED", "0")
os.environ["LBG_JOBS_STATE_PATH"] = ""  # désactive la persistance dans les tests

from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.main import app  # noqa: E402
from services import jobs as svc_jobs  # noqa: E402


def _reset_dispatch() -> None:
    svc_jobs._dispatch = svc_jobs.invoke_after_route


# --------------------------------------------------------------------------- #
# Planification déterministe
# --------------------------------------------------------------------------- #


def test_create_job_plans_deterministic_steps() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "actor_id": "user:plan",
            "objective": "vérifie l'état du backend puis cherche le site de Cursor AI",
            "auto_start": False,
        },
    )
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "queued"
    assert job["plan_source"] == "deterministic"
    caps = [s["capability"] for s in job["steps"]]
    assert "devops_probe" in caps
    assert "desktop_control" in caps
    # Périmètre restreint : toute action desktop est forcée en dry-run.
    desktop = next(s for s in job["steps"] if s["capability"] == "desktop_control")
    assert desktop["context_patch"].get("desktop_dry_run") is True


def test_create_job_non_actionable_objective_yields_note_step() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"actor_id": "user:plan", "objective": "raconte-moi une histoire de taverne", "auto_start": False},
    )
    assert r.status_code == 200
    job = r.json()
    assert len(job["steps"]) >= 1
    assert job["steps"][0]["capability"] == "unknown"


# --------------------------------------------------------------------------- #
# Exécution de fond (pilotée) jusqu'au succès
# --------------------------------------------------------------------------- #


def test_job_runs_steps_to_completion() -> None:
    calls: list[str] = []

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        calls.append(routed_to)
        return {"ok": True, "agent": "fake", "echo": text}

    svc_jobs._dispatch = fake_dispatch
    try:
        job = svc_jobs.create_job(
            actor_id="user:run",
            objective="note ceci puis note cela",
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "done"
        assert all(s.status == "done" for s in final.steps)
        assert len(calls) == len(final.steps)
    finally:
        _reset_dispatch()


def test_job_checkup_then_synthesis_two_steps_with_prior_in_prompt() -> None:
    calls: list[tuple[str, str]] = []

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        calls.append((routed_to, text))
        if routed_to == "agent.devops":
            return {
                "ok": True,
                "agent": "devops_executor",
                "result": {
                    "kind": "selfcheck",
                    "ok": True,
                    "dry_run": True,
                    "remediation_hints": ["Vérifier le service derrière healthz"],
                    "steps": [],
                },
            }
        return {"ok": True, "agent": "fake", "reply": "Voici les améliorations possibles."}

    svc_jobs._dispatch = fake_dispatch
    try:
        job = svc_jobs.create_job(
            actor_id="user:synth",
            objective="peut tu me faire un auto checkup et me dire ce qui pourrait être amélioré",
            context={"devops_dry_run": True},
            auto_start=False,
        )
        assert len(job.steps) == 2
        assert job.steps[0].capability == "devops_probe"
        assert job.steps[1].capability == "npc_dialogue"
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "done"
        assert len(calls) == 2
        assert calls[0][0] == "agent.devops"
        assert calls[1][0] == "agent.dialogue"
        assert "Vérifier" in calls[1][1] or "remediation" in calls[1][1].lower()
        assert "amélior" in calls[1][1].lower()
    finally:
        _reset_dispatch()


# --------------------------------------------------------------------------- #
# Auto-correction : échec puis retry réussi
# --------------------------------------------------------------------------- #


def test_step_self_correction_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def flaky_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"ok": False, "error": "échec transitoire simulé"}
        return {"ok": True, "agent": "fake"}

    svc_jobs._dispatch = flaky_dispatch
    try:
        job = svc_jobs.create_job(
            actor_id="user:retry",
            objective="étape unique",
            steps=[
                {
                    "capability": "unknown",
                    "routed_to": "agent.fallback",
                    "summary": "étape qui échoue puis réussit",
                    "risk_level": "low",
                    "text": "fais le travail",
                    "max_attempts": 2,
                }
            ],
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "done"
        assert final.steps[0].status == "done"
        assert final.steps[0].attempts == 2
        # La timeline doit contenir une trace de retry.
        assert any(e["kind"] == "step_retry" for e in final.events)
    finally:
        _reset_dispatch()


def test_step_fails_after_exhausting_attempts() -> None:
    def always_fail(routed_to, *, actor_id, text, context):  # noqa: ANN001
        return {"ok": False, "error": "toujours en échec"}

    svc_jobs._dispatch = always_fail
    try:
        job = svc_jobs.create_job(
            actor_id="user:fail",
            objective="étape condamnée",
            steps=[
                {
                    "capability": "unknown",
                    "routed_to": "agent.fallback",
                    "summary": "étape condamnée",
                    "risk_level": "low",
                    "text": "fais le travail",
                    "max_attempts": 2,
                }
            ],
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "failed"
        assert final.steps[0].status == "failed"
        assert final.steps[0].attempts == 2
    finally:
        _reset_dispatch()


# --------------------------------------------------------------------------- #
# Garde-fou : pause sur action à risque, reprise par token (semi-auto)
# --------------------------------------------------------------------------- #


def test_high_risk_step_waits_for_approval_then_resumes_with_token() -> None:
    dispatched: list[str] = []

    def fake_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        dispatched.append(routed_to)
        # On vérifie que l'approbation a bien été injectée après le token.
        assert context.get("devops_approval")
        return {"ok": True, "agent": "fake_devops"}

    # devops_probe doit être explicitement autorisé à l'exécution réelle (élargissement par capability).
    os.environ["LBG_JOBS_REAL_CAPABILITIES"] = "devops_probe"
    svc_jobs._dispatch = fake_dispatch
    try:
        # Étape DevOps sensible (read_log_tail) SANS dry-run ni approbation :
        # la policy doit exiger une approbation -> job en waiting_approval.
        job = svc_jobs.create_job(
            actor_id="ops:1",
            objective="lire la fin du log",
            steps=[
                {
                    "capability": "devops_probe",
                    "routed_to": "agent.devops",
                    "action_context_key": "devops_action",
                    "action": {"kind": "read_log_tail", "unit": "lbg-backend"},
                    "context_patch": {"devops_action": {"kind": "read_log_tail", "unit": "lbg-backend"}},
                    "summary": "lire la fin du log backend",
                    "risk_level": "high",
                }
            ],
            auto_start=True,
        )
        paused = svc_jobs.run_job_to_completion(job.id)
        assert paused is not None
        assert paused.status == "waiting_approval"
        assert paused.steps[0].status == "waiting_approval"
        assert dispatched == []  # rien n'a été exécuté

        # Approbation par token -> reprise et exécution réelle.
        approved = svc_jobs.approve_job(job.id, "ok-go")
        assert approved is not None
        assert approved.pre_authorized is True
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None
        assert final.status == "done"
        assert dispatched == ["agent.devops"]
    finally:
        _reset_dispatch()
        os.environ.pop("LBG_JOBS_REAL_CAPABILITIES", None)


def test_preauthorized_capability_gate_per_capability() -> None:
    """Même pré-autorisé (token), une action n'est élevée en réel que si sa capability est allowlistée."""
    seen: list[dict] = []

    def recording_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        seen.append(dict(context))
        return {"ok": True, "agent": "fake_desktop"}

    desktop_step = {
        "capability": "desktop_control",
        "routed_to": "agent.desktop",
        "action_context_key": "desktop_action",
        "action": {"kind": "open_url", "url": "https://example.org"},
        "context_patch": {"desktop_action": {"kind": "open_url", "url": "https://example.org"}, "desktop_dry_run": True},
        "summary": "ouvrir une URL",
        "risk_level": "high",
    }

    svc_jobs._dispatch = recording_dispatch
    try:
        # 1) Allowlist VIDE : reste en dry-run (pas d'approbation injectée), exécution non réelle.
        os.environ.pop("LBG_JOBS_REAL_CAPABILITIES", None)
        job = svc_jobs.create_job(actor_id="ops:gate", objective="ouvrir url", steps=[dict(desktop_step)], approval_token="tok", auto_start=True)
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None and final.status == "done"
        assert seen[-1].get("desktop_dry_run") is True
        assert seen[-1].get("desktop_approval") == "tok"

        # 2) Allowlist INCLUT desktop_control : élévation en réel (approbation injectée, dry-run retiré).
        os.environ["LBG_JOBS_REAL_CAPABILITIES"] = "desktop_control"
        job2 = svc_jobs.create_job(actor_id="ops:gate", objective="ouvrir url", steps=[dict(desktop_step)], approval_token="tok", auto_start=True)
        final2 = svc_jobs.run_job_to_completion(job2.id)
        assert final2 is not None and final2.status == "done"
        assert seen[-1].get("desktop_approval")
        assert "desktop_dry_run" not in seen[-1]
    finally:
        _reset_dispatch()
        os.environ.pop("LBG_JOBS_REAL_CAPABILITIES", None)


def test_job_capabilities_inventory_direct_no_llm() -> None:
    """Inventaire registry : exécution locale, catalogue structuré dans le résultat."""
    calls: list[str] = []

    def recording_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        calls.append(routed_to)
        return {"ok": True, "reply": "should not run"}

    step_def = {
        "capability": "npc_dialogue",
        "routed_to": "agent.dialogue",
        "action_context_key": "",
        "action": {},
        "context_patch": {"_capabilities_inventory": True},
        "summary": "inventaire",
        "risk_level": "medium",
    }

    svc_jobs._dispatch = recording_dispatch
    try:
        job = svc_jobs.create_job(
            actor_id="pilot:jobs",
            objective="liste des agents et capacités",
            steps=[dict(step_def)],
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None and final.status == "done"
        assert calls == []
        res = final.steps[0].result
        assert res is not None
        assert res.get("agent") == "jobs.capabilities_inventory"
        catalog = res.get("capabilities_catalog")
        assert isinstance(catalog, list) and len(catalog) >= 3
        names = {row["capability"] for row in catalog}
        assert "npc_dialogue" in names
        assert "desktop_control" in names
        assert "npc_dialogue" in (res.get("reply") or "")
    finally:
        _reset_dispatch()


def test_capabilities_inventory_action_matrix_with_network() -> None:
    devices = [
        {
            "host": "192.168.0.10",
            "label": "pc-windows",
            "reachable": True,
            "action_suggestions": ["desktop_control", "devops_probe"],
            "open_ports": [5005, 3389],
        },
        {
            "host": "192.168.0.140",
            "label": "core",
            "reachable": True,
            "action_suggestions": ["devops_probe", "network_inventory"],
            "open_ports": [8010],
        },
    ]
    out = svc_jobs._run_capabilities_inventory(network_devices=devices)
    matrix = out.get("action_matrix")
    assert isinstance(matrix, list) and len(matrix) == 2
    hosts = {row["host"] for row in matrix}
    assert "192.168.0.10" in hosts
    pc = next(r for r in matrix if r["host"] == "192.168.0.10")
    caps = {c["capability"] for c in pc["suggested_capabilities"]}
    assert "desktop_control" in caps
    assert "devops_probe" in caps
    assert "Matrice actions" in (out.get("reply") or "")


def test_job_propagates_pilot_approval_token_to_desktop_context() -> None:
    """Token saisi à la création → ``context.desktop_approval`` (worker Windows)."""
    seen: list[dict] = []

    def recording_dispatch(routed_to, *, actor_id, text, context):  # noqa: ANN001
        seen.append(dict(context))
        return {"ok": True, "outcome": "dry_run", "agent": "fake_desktop"}

    desktop_step = {
        "capability": "desktop_control",
        "routed_to": "agent.desktop",
        "action_context_key": "desktop_action",
        "action": {"kind": "search_web_open", "query": "cursor ai"},
        "context_patch": {
            "desktop_action": {"kind": "search_web_open", "query": "cursor ai"},
            "desktop_dry_run": True,
        },
        "summary": "recherche web",
        "risk_level": "high",
    }

    svc_jobs._dispatch = recording_dispatch
    try:
        os.environ.pop("LBG_JOBS_REAL_CAPABILITIES", None)
        job = svc_jobs.create_job(
            actor_id="pilot:jobs",
            objective="cherche cursor ai",
            steps=[dict(desktop_step)],
            approval_token="CHANGE-MOI",
            auto_start=True,
        )
        final = svc_jobs.run_job_to_completion(job.id)
        assert final is not None and final.status == "done"
        assert final.stored_approval_token == "CHANGE-MOI"
        assert seen[-1].get("desktop_approval") == "CHANGE-MOI"
    finally:
        _reset_dispatch()


def test_approve_rejects_empty_token() -> None:
    job = svc_jobs.create_job(
        actor_id="ops:2",
        objective="action sensible",
        steps=[
            {
                "capability": "devops_probe",
                "routed_to": "agent.devops",
                "action_context_key": "devops_action",
                "action": {"kind": "systemd_restart", "unit": "lbg-backend"},
                "context_patch": {"devops_action": {"kind": "systemd_restart", "unit": "lbg-backend"}},
                "summary": "restart backend",
                "risk_level": "high",
            }
        ],
        auto_start=True,
    )
    svc_jobs.run_job_to_completion(job.id)
    # Token vide refusé par l'API.
    client = TestClient(app)
    r = client.post(f"/v1/jobs/{job.id}/approve", json={"token": ""})
    assert r.status_code == 422  # validation pydantic min_length


# --------------------------------------------------------------------------- #
# Annulation
# --------------------------------------------------------------------------- #


def test_cancel_job_stops_pending_steps() -> None:
    job = svc_jobs.create_job(
        actor_id="user:cancel",
        objective="note un puis note deux",
        auto_start=False,
    )
    cancelled = svc_jobs.cancel_job(job.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert all(s.status in ("skipped",) for s in cancelled.steps)
    # Un advance après annulation ne relance rien.
    after = svc_jobs.advance_job(job.id)
    assert after.status == "cancelled"


# --------------------------------------------------------------------------- #
# API : liste et 404
# --------------------------------------------------------------------------- #


def test_list_jobs_filtered_by_actor() -> None:
    client = TestClient(app)
    client.post("/v1/jobs", json={"actor_id": "user:list-a", "objective": "note a", "auto_start": False})
    client.post("/v1/jobs", json={"actor_id": "user:list-a", "objective": "note b", "auto_start": False})
    r = client.get("/v1/jobs", params={"actor_id": "user:list-a"})
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) >= 2
    assert all(j["actor_id"] == "user:list-a" for j in jobs)


def test_get_unknown_job_returns_404() -> None:
    client = TestClient(app)
    r = client.get("/v1/jobs/does-not-exist")
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Persistance : fichier (roundtrip) + dégradation Redis
# --------------------------------------------------------------------------- #


def test_persistence_file_roundtrip(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "jobs_state.json"
    monkeypatch.setenv("LBG_JOBS_STATE_PATH", str(path))
    monkeypatch.delenv("LBG_JOBS_REDIS_URL", raising=False)
    svc_jobs._redis_resolved_for = None
    svc_jobs._redis_client = None

    job = svc_jobs.create_job(actor_id="persist", objective="note x puis note y", auto_start=False)
    assert path.exists()
    assert svc_jobs.persistence_backend() == "file"

    # Simule un reboot : on retire de la mémoire puis on recharge depuis le disque.
    svc_jobs._jobs.pop(job.id, None)
    assert svc_jobs.get_job(job.id) is None
    svc_jobs._load_on_boot()
    reloaded = svc_jobs.get_job(job.id)
    assert reloaded is not None
    assert reloaded.objective == job.objective
    assert len(reloaded.steps) == len(job.steps)


def test_redis_url_set_but_unavailable_degrades(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    # Port volontairement fermé : la résolution Redis doit échouer proprement.
    monkeypatch.setenv("LBG_JOBS_REDIS_URL", "redis://127.0.0.1:6399/0")
    monkeypatch.setenv("LBG_JOBS_STATE_PATH", str(tmp_path / "fallback.json"))
    svc_jobs._redis_resolved_for = None
    svc_jobs._redis_client = None
    try:
        job = svc_jobs.create_job(actor_id="redisdeg", objective="note z", auto_start=False)
        assert job is not None
        # Pas d'exception, et bascule vers le fichier (ou mémoire).
        assert svc_jobs.persistence_backend() in ("file", "memory")
    finally:
        svc_jobs._redis_resolved_for = None
        svc_jobs._redis_client = None


class _FakeRedis:
    """Mini client Redis en mémoire (set/get + set d'index) pour tester le layout `index`."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.set_calls = 0

    def set(self, key, value):  # noqa: ANN001
        self.kv[key] = value
        self.set_calls += 1

    def get(self, key):  # noqa: ANN001
        return self.kv.get(key)

    def sadd(self, key, *members):  # noqa: ANN001
        self.sets.setdefault(key, set()).update(str(m) for m in members)

    def smembers(self, key):  # noqa: ANN001
        return set(self.sets.get(key, set()))


def test_redis_index_layout_per_job(monkeypatch) -> None:  # noqa: ANN001
    """Layout `index` : une clé par job + set d'index, et rechargement par index."""
    fake = _FakeRedis()
    monkeypatch.setenv("LBG_JOBS_REDIS_URL", "redis://fake/0")
    monkeypatch.setenv("LBG_JOBS_REDIS_LAYOUT", "index")
    monkeypatch.setenv("LBG_JOBS_REDIS_PREFIX", "lbg:test:jobs")
    monkeypatch.setattr(svc_jobs, "_get_redis", lambda: fake)
    try:
        job_a = svc_jobs.create_job(actor_id="idx", objective="note alpha", auto_start=False)
        job_b = svc_jobs.create_job(actor_id="idx", objective="note beta", auto_start=False)

        # Deux clés job distinctes + index peuplé.
        assert svc_jobs._redis_job_key(job_a.id) in fake.kv
        assert svc_jobs._redis_job_key(job_b.id) in fake.kv
        assert {job_a.id, job_b.id} <= fake.smembers(svc_jobs._redis_index_key())

        # Reboot simulé : vider la mémoire puis recharger depuis l'index.
        svc_jobs._jobs.clear()
        assert svc_jobs.get_job(job_a.id) is None
        svc_jobs._load_on_boot()
        assert svc_jobs.get_job(job_a.id) is not None
        assert svc_jobs.get_job(job_b.id) is not None
        assert svc_jobs.persistence_backend() == "redis"
    finally:
        svc_jobs._jobs.pop(job_a.id, None)
        svc_jobs._jobs.pop(job_b.id, None)
