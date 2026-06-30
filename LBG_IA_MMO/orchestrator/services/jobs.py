"""
Moteur de jobs autonome ("type Cowork", sous garde-fous).

Idée : l'utilisateur décrit un **objectif** en langage naturel ; le moteur le
**planifie** (services.planner), puis exécute les étapes **en tâche de fond**,
**observe** chaque résultat et **se corrige** (retry borné) jusqu'au succès ou
à l'échec, sans jamais contourner la policy d'actions de l'orchestrateur.

Différences clés avec un agent "grand public" :

- chaque étape passe par ``evaluate_action_policy`` avant dispatch ;
- les actions à effet de bord restent en **dry-run** (périmètre restreint) sauf
  si le job est **pré-autorisé** par un token (autonomie semi-auto) ;
- une étape à risque non autorisée met le job en ``waiting_approval`` (il reprend
  après ``approve_job``), au lieu d'agir en aveugle.

Le moteur est volontairement **testable** : l'avancement se fait étape par étape
via ``advance_job`` (pur, sans thread). Le thread daemon (``ensure_started``) ne
fait qu'appeler ``advance_job`` en boucle quand ``LBG_JOBS_RUNNER_ENABLED`` est
actif (désactivé par défaut, comme le Brain).
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from lbg_agents.dispatch import invoke_after_route

from services import planner as svc_planner
from services import experience_memory as svc_memory
from services.action_policy import evaluate_action_policy
from shared_registry import capability_registry

# Type du dispatcher (injectable pour les tests).
Dispatcher = Callable[..., dict[str, Any]]

JOB_STATUSES = (
    "queued",
    "planning",
    "running",
    "waiting_approval",
    "done",
    "failed",
    "cancelled",
)
STEP_STATUSES = (
    "queued",
    "running",
    "done",
    "failed",
    "skipped",
    "waiting_approval",
)

# Clé d'action -> (clé d'approbation, drapeau dry-run) pour élever en exécution réelle.
_APPROVAL_BY_ACTION_KEY = {
    "desktop_action": ("desktop_approval", "desktop_dry_run"),
    "devops_action": ("devops_approval", "devops_dry_run"),
    "opengame_action": ("opengame_approval", "opengame_dry_run"),
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def runner_enabled() -> bool:
    return _truthy(os.environ.get("LBG_JOBS_RUNNER_ENABLED", "0"))


def runner_interval_s() -> float:
    raw = os.environ.get("LBG_JOBS_RUNNER_INTERVAL_S", "2").strip()
    try:
        n = float(raw)
    except ValueError:
        n = 2.0
    return max(0.2, min(n, 60.0))


def default_max_attempts() -> int:
    raw = os.environ.get("LBG_JOBS_STEP_MAX_ATTEMPTS", "2").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return max(1, min(n, 6))


def continue_on_step_failure() -> bool:
    return _truthy(os.environ.get("LBG_JOBS_CONTINUE_ON_STEP_FAILURE", "0"))


def default_max_replans() -> int:
    """Nombre de **re-planifications** automatiques après épuisement des retries d'une étape.

    Auto-correction de niveau objectif (« Cowork ») : quand une étape échoue malgré ses
    retries, on re-planifie l'objectif (avec le journal d'erreurs) au lieu d'abandonner.
    Borné pour éviter les boucles. Défaut 1, 0 pour désactiver.
    """
    raw = os.environ.get("LBG_JOBS_MAX_REPLANS", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 1
    return max(0, min(n, 4))


def real_capabilities() -> frozenset[str]:
    """Capabilities autorisées à s'exécuter **réellement** (effet de bord) dans un job pré-autorisé.

    Élargissement contrôlé du périmètre, **capability par capability** : par défaut **vide**
    (tout reste en dry-run même avec un token). L'opérateur élargit explicitement via
    ``LBG_JOBS_REAL_CAPABILITIES`` (liste séparée par des virgules), p. ex.
    ``LBG_JOBS_REAL_CAPABILITIES="desktop_control,devops_probe"``.
    """
    raw = os.environ.get("LBG_JOBS_REAL_CAPABILITIES", "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def jobs_state_path() -> str:
    return os.environ.get("LBG_JOBS_STATE_PATH", "/var/lib/lbg/jobs/state.json").strip()


def jobs_redis_url() -> str:
    """URL Redis optionnelle (ex. ``redis://127.0.0.1:6379/0``). Vide => persistance fichier JSON."""
    return os.environ.get("LBG_JOBS_REDIS_URL", "").strip()


def jobs_redis_key() -> str:
    """Clé du snapshot unique (layout ``snapshot``, rétro-compatibilité)."""
    return os.environ.get("LBG_JOBS_REDIS_KEY", "lbg:jobs:state").strip() or "lbg:jobs:state"


def jobs_redis_layout() -> str:
    """Disposition Redis : ``index`` (clé par job + index, recommandé) | ``snapshot`` (clé unique)."""
    v = os.environ.get("LBG_JOBS_REDIS_LAYOUT", "index").strip().lower()
    return "snapshot" if v == "snapshot" else "index"


def jobs_redis_prefix() -> str:
    """Préfixe des clés en layout ``index`` (clés ``{prefix}:job:{id}`` + set ``{prefix}:index``)."""
    return os.environ.get("LBG_JOBS_REDIS_PREFIX", "lbg:jobs").strip() or "lbg:jobs"


def _redis_index_key() -> str:
    return f"{jobs_redis_prefix()}:index"


def _redis_job_key(job_id: str) -> str:
    return f"{jobs_redis_prefix()}:job:{job_id}"


def _expected_token() -> str:
    return os.environ.get("LBG_JOBS_APPROVAL_TOKEN", "").strip()


def token_is_valid(token: str | None) -> bool:
    """Token d'approbation valide : non vide et conforme à l'env si celui-ci est défini."""
    t = (token or "").strip()
    if not t:
        return False
    expected = _expected_token()
    return (t == expected) if expected else True


def _capture_approval_token(token: str | None) -> str | None:
    """Conserve le jeton opérateur pour propagation ``desktop_approval`` / ``devops_approval`` / etc."""
    t = (token or "").strip()
    if not token_is_valid(t):
        return None
    return t


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _inject_approval_tokens(job: Job, step: JobStep, ctx: dict[str, Any]) -> None:
    """Propage le token du formulaire jobs vers les clés attendues par les agents (worker desktop, DevOps…)."""
    if step.action_context_key not in _APPROVAL_BY_ACTION_KEY:
        return
    approval_key, _ = _APPROVAL_BY_ACTION_KEY[step.action_context_key]
    if _non_empty_str(ctx.get(approval_key)):
        return
    tok = (job.stored_approval_token or "").strip()
    if not tok and job.pre_authorized:
        expected = _expected_token()
        tok = expected if expected else ""
    if tok:
        ctx[approval_key] = tok


# --------------------------------------------------------------------------- #
# Modèle
# --------------------------------------------------------------------------- #


@dataclass
class JobStep:
    id: str
    capability: str
    routed_to: str
    summary: str
    risk_level: str
    text: str
    action_context_key: str | None = None
    action: dict[str, Any] = field(default_factory=dict)
    context_patch: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    attempts: int = 0
    max_attempts: int = 1
    policy: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class Job:
    id: str
    actor_id: str
    objective: str
    status: str = "queued"
    plan_source: str | None = None
    pre_authorized: bool = False
    """Token saisi à la création ou via ``/approve`` (non renvoyé par l'API publique)."""
    stored_approval_token: str | None = None
    cursor: int = 0
    base_context: dict[str, Any] = field(default_factory=dict)
    steps: list[JobStep] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_log: list[dict[str, Any]] = field(default_factory=list)
    replans: int = 0
    result_summary: str | None = None
    trace_id: str = ""
    created_ts: float = 0.0
    updated_ts: float = 0.0


_lock = threading.RLock()
_jobs: dict[str, Job] = {}
_thread: threading.Thread | None = None
_stop = threading.Event()
_listeners: list[Callable[[Job, dict[str, Any]], None]] = []

# Dispatcher courant (les tests peuvent remplacer ``_dispatch``).
_dispatch: Dispatcher = invoke_after_route


def register_listener(listener: Callable[[Job, dict[str, Any]], None]) -> None:
    with _lock:
        _listeners.append(listener)


def unregister_listener(listener: Callable[[Job, dict[str, Any]], None]) -> None:
    with _lock:
        if listener in _listeners:
            _listeners.remove(listener)


def _now() -> float:
    return float(time.time())


def _new_id() -> str:
    return uuid.uuid4().hex


def _emit(job: Job, kind: str, **detail: Any) -> None:
    evt = {"ts": _now(), "kind": kind, **detail}
    job.events.append(evt)
    print(
        json.dumps(
            {"event": f"orchestrator.jobs.{kind}", "job_id": job.id, "trace_id": job.trace_id, **detail},
            ensure_ascii=False,
        )
    )
    with _lock:
        for listener in _listeners:
            try:
                listener(job, evt)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Persistance best-effort (jamais bloquante, jamais d'exception remontée)
# --------------------------------------------------------------------------- #


def _serialize_job(job: Job) -> dict[str, Any]:
    d = asdict(job)
    return d


# Client Redis paresseux : None tant que non résolu, False si indisponible (dégradation propre).
_redis_client: Any = None
_redis_resolved_for: str | None = None


def _get_redis() -> Any:
    """Retourne un client Redis prêt, ou ``None`` (dégradation vers fichier/mémoire).

    Lazy + best-effort : si l'URL change, on réessaie ; toute erreur (paquet absent,
    connexion impossible) renvoie ``None`` sans jamais lever.
    """
    global _redis_client, _redis_resolved_for
    url = jobs_redis_url()
    if not url:
        return None
    if _redis_resolved_for == url:
        return _redis_client or None
    _redis_resolved_for = url
    _redis_client = None
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(url, socket_connect_timeout=1.5, socket_timeout=1.5)
        client.ping()
        _redis_client = client
        layout = jobs_redis_layout()
        print(
            json.dumps(
                {
                    "event": "orchestrator.jobs.persistence",
                    "backend": "redis",
                    "layout": layout,
                    "key": jobs_redis_key() if layout == "snapshot" else jobs_redis_prefix(),
                }
            )
        )
    except Exception as e:
        print(
            json.dumps(
                {"event": "orchestrator.jobs.persistence_degraded", "backend": "file_or_memory", "error": f"{type(e).__name__}: {e}"}
            )
        )
        _redis_client = None
    return _redis_client


def persistence_backend() -> str:
    """Backend de persistance effectif : ``redis`` | ``file`` | ``memory`` (observabilité)."""
    if jobs_redis_url() and _get_redis() is not None:
        return "redis"
    return "file" if jobs_state_path() else "memory"


def _snapshot_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ts": _now(),
        "jobs": [_serialize_job(j) for j in _jobs.values()],
    }


def _persist_redis_index(client: Any, job: Job | None) -> bool:
    """Layout ``index`` : une clé par job + un set d'index. Retourne True si écrit."""
    try:
        targets = [job] if job is not None else list(_jobs.values())
        idx_key = _redis_index_key()
        for j in targets:
            client.set(_redis_job_key(j.id), json.dumps(_serialize_job(j), ensure_ascii=False))
            client.sadd(idx_key, j.id)
        return True
    except Exception:
        return False


def _persist_redis_snapshot(client: Any) -> bool:
    try:
        client.set(jobs_redis_key(), json.dumps(_snapshot_payload(), ensure_ascii=False))
        return True
    except Exception:
        return False


def _persist_locked(job: Job | None = None) -> None:
    """Persiste l'état. Best-effort : ne lève jamais.

    Si ``job`` est fourni en layout Redis ``index``, on n'écrit que cette clé (+ index),
    évitant de réécrire tous les jobs à chaque mutation (objectif multivers à grande échelle).
    """
    # 1) Redis si configuré et disponible.
    client = _get_redis()
    if client is not None:
        ok = _persist_redis_index(client, job) if jobs_redis_layout() == "index" else _persist_redis_snapshot(client)
        if ok:
            return
        # Bascule best-effort vers le fichier si l'écriture Redis échoue.

    # 2) Fichier JSON (atomique, snapshot complet).
    path = jobs_state_path()
    if not path:
        return
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_snapshot_payload(), f, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        # Best-effort : l'état en mémoire reste la source de vérité courante.
        return


def _decode(raw: Any) -> Any:
    return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw


def _job_dicts_from_redis_index(client: Any) -> list[dict[str, Any]] | None:
    try:
        ids = client.smembers(_redis_index_key())
        if not ids:
            return []
        out: list[dict[str, Any]] = []
        for rid in ids:
            jid = _decode(rid)
            raw = client.get(_redis_job_key(jid))
            if not raw:
                continue
            data = json.loads(_decode(raw))
            if isinstance(data, dict):
                out.append(data)
        return out
    except Exception:
        return None


def _job_dicts_on_boot() -> list[dict[str, Any]]:
    # 1) Redis prioritaire.
    client = _get_redis()
    if client is not None:
        if jobs_redis_layout() == "index":
            jobs = _job_dicts_from_redis_index(client)
            if jobs is not None:
                return jobs
        else:
            try:
                raw = client.get(jobs_redis_key())
                if raw:
                    data = json.loads(_decode(raw))
                    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
                        return data["jobs"]
                return []
            except Exception:
                pass

    # 2) Fichier JSON (snapshot).
    path = jobs_state_path()
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("jobs"), list):
            return data["jobs"]
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return []


def _load_on_boot() -> None:
    jobs_raw = _job_dicts_on_boot()
    with _lock:
        for jd in jobs_raw:
            if not isinstance(jd, dict) or not isinstance(jd.get("id"), str):
                continue
            try:
                steps = [JobStep(**sd) for sd in jd.get("steps", []) if isinstance(sd, dict)]
                job = Job(**{**jd, "steps": steps})
            except (TypeError, ValueError):
                continue
            # Un job laissé "running"/"planning" au reboot redevient reprenable.
            if job.status in ("running", "planning"):
                job.status = "queued"
            _jobs[job.id] = job


# --------------------------------------------------------------------------- #
# API service
# --------------------------------------------------------------------------- #


def create_job(
    *,
    actor_id: str,
    objective: str,
    context: dict[str, Any] | None = None,
    approval_token: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    auto_start: bool = True,
    model: str | None = None,
    planner: str | None = None,
) -> Job:
    """Crée un job. Planifie immédiatement (sauf si ``steps`` fourni explicitement)."""
    base_ctx = dict(context) if isinstance(context, dict) else {}
    if model:
        base_ctx["_planner_model"] = model
    if planner:
        base_ctx["_planner"] = planner
    trace_id = base_ctx.get("_trace_id")

    trace_id = trace_id if isinstance(trace_id, str) and trace_id.strip() else _new_id()
    base_ctx["_trace_id"] = trace_id

    captured = _capture_approval_token(approval_token)
    job = Job(
        id=_new_id(),
        actor_id=actor_id,
        objective=objective.strip(),
        base_context=base_ctx,
        pre_authorized=captured is not None,
        stored_approval_token=captured,
        trace_id=trace_id,
        created_ts=_now(),
        updated_ts=_now(),
    )
    _emit(job, "created", actor_id=actor_id, objective=job.objective[:200], pre_authorized=job.pre_authorized)

    if steps is not None:
        job.steps = [_build_step(sd) for sd in steps]
        job.plan_source = "explicit"
        _emit(job, "planned", source="explicit", n_steps=len(job.steps))
        job.status = "running" if (auto_start and job.steps) else "queued"
    else:
        _plan_into_job(job)
        job.status = "running" if (auto_start and job.steps) else "queued"
        if not job.steps:
            job.status = "done"
            job.result_summary = "Aucune étape planifiable pour cet objectif."

    job.updated_ts = _now()
    with _lock:
        _jobs[job.id] = job
        _persist_locked(job)
    return _clone(job)


def _build_step(sd: dict[str, Any]) -> JobStep:
    return JobStep(
        id=_new_id(),
        capability=str(sd.get("capability") or "unknown"),
        routed_to=str(sd.get("routed_to") or "agent.fallback"),
        summary=str(sd.get("summary") or ""),
        risk_level=str(sd.get("risk_level") or "low"),
        text=str(sd.get("text") or sd.get("summary") or ""),
        action_context_key=(sd.get("action_context_key") if isinstance(sd.get("action_context_key"), str) else None),
        action=dict(sd["action"]) if isinstance(sd.get("action"), dict) else {},
        context_patch=dict(sd["context_patch"]) if isinstance(sd.get("context_patch"), dict) else {},
        max_attempts=int(sd.get("max_attempts") or default_max_attempts()),
    )


def _recall_memories(objective: str) -> list[dict[str, Any]]:
    try:
        return svc_memory.recall_similar(objective, k=3)
    except Exception:
        return []


def _plan_into_job(job: Job) -> None:
    job.status = "planning"
    memories = _recall_memories(job.objective)
    plan = svc_planner.plan_objective(
        job.objective, job.base_context, error_log=job.error_log or None, memories=memories or None
    )
    job.plan_source = plan.source
    job.steps = [_build_step({**s.as_dict(), "max_attempts": default_max_attempts()}) for s in plan.steps]
    _emit(job, "planned", source=plan.source, n_steps=len(job.steps), reason=plan.reason, memories=len(memories))


def get_job(job_id: str) -> Job | None:
    with _lock:
        job = _jobs.get(job_id)
        return _clone(job) if job else None


def list_jobs(actor_id: str | None = None) -> list[Job]:
    with _lock:
        jobs = list(_jobs.values())
    if actor_id:
        jobs = [j for j in jobs if j.actor_id == actor_id]
    jobs.sort(key=lambda j: j.created_ts, reverse=True)
    return [_clone(j) for j in jobs]


def approve_job(job_id: str, token: str | None) -> Job | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        captured = _capture_approval_token(token)
        if captured is None:
            _emit(job, "approval_rejected", reason="invalid_token")
            return _clone(job)
        job.pre_authorized = True
        job.stored_approval_token = captured
        if job.status == "waiting_approval":
            job.status = "running"
            # L'étape en attente repart en queued pour être réévaluée avec approbation.
            for st in job.steps:
                if st.status == "waiting_approval":
                    st.status = "queued"
        _emit(job, "approved")
        job.updated_ts = _now()
        _persist_locked(job)
        return _clone(job)


def cancel_job(job_id: str) -> Job | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        if job.status in ("done", "failed", "cancelled"):
            return _clone(job)
        job.status = "cancelled"
        for st in job.steps:
            if st.status in ("queued", "running", "waiting_approval"):
                st.status = "skipped"
        _emit(job, "cancelled")
        job.updated_ts = _now()
        _persist_locked(job)
        return _clone(job)


def _clone(job: Job) -> Job:
    steps = [JobStep(**asdict(s)) for s in job.steps]
    data = asdict(job)
    data["steps"] = steps
    return Job(**data)


# --------------------------------------------------------------------------- #
# Boucle observe -> agit -> corrige (une étape par appel)
# --------------------------------------------------------------------------- #


def _step_succeeded(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return False
    if isinstance(result.get("error"), str) and result.get("error"):
        return False
    res = result.get("result")
    if isinstance(res, dict) and res.get("ok") is False:
        return False
    return True


# Issues "techniquement ok" mais qui ne répondent pas à l'objectif (succès trompeur).
_MISLEADING_OUTCOMES = frozenset(
    {"bad_request", "unknown_kind", "allowlist_denied", "forbidden", "approval_required", "approval_denied"}
)


def _result_outcome(result: dict[str, Any]) -> str:
    outcome = result.get("outcome")
    if not isinstance(outcome, str):
        res = result.get("result")
        if isinstance(res, dict) and isinstance(res.get("outcome"), str):
            outcome = res["outcome"]
    return outcome if isinstance(outcome, str) else ""


def _step_satisfies(step: JobStep, result: dict[str, Any]) -> tuple[bool, str | None]:
    """Validation **sémantique** (rapatriée de P03 ``misleading_success``) : l'étape a-t-elle
    réellement répondu à son intention, ou est-ce un succès en trompe-l'œil ?"""
    outcome = _result_outcome(result)
    if outcome in _MISLEADING_OUTCOMES:
        return False, f"outcome={outcome}"
    # open_app : un vrai succès renvoie outcome ok/dry_run (worker) ou échoue franchement.
    kind = step.action.get("kind") if isinstance(step.action, dict) else None
    if kind == "open_app" and outcome and outcome not in ("ok", "dry_run"):
        return False, f"open_app outcome inattendu ({outcome})"
    return True, None


def _evaluate_step(step: JobStep, result: dict[str, Any]) -> tuple[bool, str | None]:
    """Verdict combiné succès technique + adéquation sémantique. Retourne (ok, raison_échec)."""
    if not _step_succeeded(result):
        err = result.get("error") if isinstance(result, dict) else None
        return False, err if isinstance(err, str) and err else "Étape en échec."
    ok, reason = _step_satisfies(step, result)
    if not ok:
        return False, f"Succès trompeur : {reason}"
    return True, None


def _is_elevated(job: Job, step: JobStep) -> bool:
    """Une action à effet de bord est élevée en réel uniquement si :
    job pré-autorisé (token) ET capability explicitement dans l'allowlist d'exécution réelle.
    """
    return (
        job.pre_authorized
        and step.action_context_key in _APPROVAL_BY_ACTION_KEY
        and step.capability in real_capabilities()
    )


def _prior_completed_steps(job: Job, before_step_id: str) -> list[dict[str, Any]]:
    """Étapes déjà terminées avant ``before_step_id`` (pour synthèse dialogue)."""
    out: list[dict[str, Any]] = []
    for s in job.steps:
        if s.id == before_step_id:
            break
        if s.status == "done" and isinstance(s.result, dict):
            out.append(
                {
                    "capability": s.capability,
                    "summary": s.summary,
                    "text": s.text,
                    "result": s.result,
                }
            )
    return out


def _format_prior_for_synthesis(prior: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for p in prior:
        cap = str(p.get("capability") or "")
        res = p.get("result")
        if cap == "network_inventory" and isinstance(res, dict):
            devices = res.get("devices")
            if isinstance(devices, list) and devices:
                lines = []
                for d in devices:
                    if not isinstance(d, dict):
                        continue
                    mark = "OK" if d.get("reachable") else "KO"
                    host = d.get("host")
                    hn = d.get("hostname")
                    host_s = f"{host}" + (f" ({hn})" if hn else "")
                    sugg = d.get("action_suggestions") or []
                    extra = f" → {', '.join(str(s) for s in sugg)}" if sugg else ""
                    lines.append(f"- {d.get('label') or d.get('server_id')} [{host_s}] : {mark}{extra}")
                if lines:
                    chunks.append("Inventaire réseau LAN :\n" + "\n".join(lines))
            if isinstance(res.get("reply"), str) and res["reply"].strip():
                chunks.append(res["reply"].strip()[:2500])
        if isinstance(res, dict):
            matrix = res.get("action_matrix")
            if isinstance(matrix, list) and matrix:
                chunks.append(_format_action_matrix_text(matrix))
        if cap == "devops_probe" and isinstance(res, dict):
            inner = res.get("result") if isinstance(res.get("result"), dict) else res
            if isinstance(inner, dict):
                hints = inner.get("remediation_hints")
                if isinstance(hints, list) and hints:
                    lines = [h.strip() for h in hints if isinstance(h, str) and h.strip()]
                    if lines:
                        chunks.append("Pistes de remédiation DevOps :\n" + "\n".join(f"- {x}" for x in lines))
                for st in inner.get("steps") or []:
                    if isinstance(st, dict) and st.get("healthy") is False:
                        chunks.append(
                            f"Étape selfcheck KO ({st.get('kind')}) : "
                            f"{json.dumps(st.get('result'), ensure_ascii=False)[:600]}"
                        )
                chunks.append(
                    f"Selfcheck global : ok={inner.get('ok')} dry_run={inner.get('dry_run')}"
                )
        if isinstance(res, dict):
            chunks.append(json.dumps(res, ensure_ascii=False)[:2500])
    return "\n\n".join(chunks) if chunks else "(aucun résultat structuré)"


def _capabilities_catalog_payload() -> list[dict[str, Any]]:
    """Snapshot read-only du registry pour les jobs « liste agents / capabilities »."""
    rows: list[dict[str, Any]] = []
    for cap in capability_registry.list():
        rows.append(
            {
                "capability": cap.name,
                "routed_to": cap.routed_to,
                "description": cap.description,
                "risk_level": cap.risk_level,
                "mode": cap.mode,
                "action_context_key": cap.action_context_key,
                "tags": list(cap.tags),
            }
        )
    rows.sort(key=lambda r: str(r.get("capability") or ""))
    return rows


def _format_capabilities_catalog_text(catalog: list[dict[str, Any]]) -> str:
    lines = [f"Inventaire registry — {len(catalog)} capability(s) — instantané T", ""]
    for row in catalog:
        desc = str(row.get("description") or "").strip()
        tags = row.get("tags") or []
        tag_s = f" | tags: {', '.join(str(t) for t in tags)}" if tags else ""
        act = row.get("action_context_key")
        act_s = f" | action: {act}" if act else ""
        extra = f" — {desc}" if desc else ""
        lines.append(
            f"• {row.get('capability')} → {row.get('routed_to')} "
            f"({row.get('risk_level')}, mode {row.get('mode')}){act_s}{tag_s}{extra}"
        )
    return "\n".join(lines)


def _network_devices_from_job(job: Job) -> list[dict[str, Any]] | None:
    for st in job.steps:
        if st.capability != "network_inventory" or st.status != "done":
            continue
        res = st.result
        if isinstance(res, dict) and isinstance(res.get("devices"), list):
            return res["devices"]
    return None


def _build_action_matrix(
    devices: list[dict[str, Any]] | None,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Croise inventaire LAN et registry : capabilities suggérées par appareil."""
    if not devices:
        return []
    by_cap = {str(row.get("capability") or ""): row for row in catalog if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    for d in devices:
        if not isinstance(d, dict) or not d.get("reachable"):
            continue
        suggestions = d.get("action_suggestions")
        if not isinstance(suggestions, list):
            suggestions = []
        cap_rows = []
        for cap_name in suggestions:
            spec = by_cap.get(str(cap_name))
            if spec is None:
                continue
            cap_rows.append(
                {
                    "capability": cap_name,
                    "routed_to": spec.get("routed_to"),
                    "risk_level": spec.get("risk_level"),
                    "description": spec.get("description"),
                }
            )
        if not cap_rows:
            continue
        rows.append(
            {
                "host": d.get("host"),
                "hostname": d.get("hostname"),
                "label": d.get("label"),
                "device_hint": d.get("device_hint"),
                "open_ports": d.get("open_ports") or [],
                "suggested_capabilities": cap_rows,
            }
        )
    rows.sort(key=lambda r: str(r.get("host") or ""))
    return rows


def _format_action_matrix_text(matrix: list[dict[str, Any]]) -> str:
    if not matrix:
        return ""
    lines = [f"Matrice actions LAN × capabilities — {len(matrix)} appareil(s)", ""]
    for row in matrix:
        host = row.get("host", "?")
        label = row.get("label") or host
        hostname = row.get("hostname")
        host_s = f"{host}" + (f" ({hostname})" if hostname else "")
        caps = row.get("suggested_capabilities") or []
        cap_s = ", ".join(
            f"{c.get('capability')}→{c.get('routed_to')}" for c in caps if isinstance(c, dict)
        )
        lines.append(f"• {label} [{host_s}] : {cap_s or '—'}")
    return "\n".join(lines)


def _run_capabilities_inventory(
    *,
    network_devices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Lecture locale du registry : résultat structuré exploitable immédiatement (pas de LLM)."""
    catalog = _capabilities_catalog_payload()
    action_matrix = _build_action_matrix(network_devices, catalog)
    reply_parts = [_format_capabilities_catalog_text(catalog)]
    matrix_text = _format_action_matrix_text(action_matrix)
    if matrix_text:
        reply_parts.append(matrix_text)
    return {
        "ok": True,
        "agent": "jobs.capabilities_inventory",
        "handler": "registry_snapshot",
        "reply": "\n\n".join(reply_parts),
        "capabilities_catalog": catalog,
        "n_capabilities": len(catalog),
        "action_matrix": action_matrix,
        "n_action_matrix_rows": len(action_matrix),
        "source": "orchestrator_registry",
        "ts": _now(),
    }


def _dispatch_text_for_step(job: Job, step: JobStep, ctx: dict[str, Any]) -> str:
    """Texte envoyé au handler ; enrichi si étape de synthèse après selfcheck / DevOps."""
    if ctx.get("_capabilities_inventory") or step.context_patch.get("_capabilities_inventory"):
        catalog = ctx.get("_capabilities_catalog")
        if not isinstance(catalog, list):
            catalog = _capabilities_catalog_payload()
        block = json.dumps(catalog, ensure_ascii=False, indent=2)
        return (
            f"{step.text.strip()}\n\n---\n"
            "Catalogue des capabilities (registry orchestrateur) — résumer en français, "
            "par agent/handler (routed_to) et capacité :\n"
            f"{block[:8000]}"
        )
    if not ctx.get("_job_synthesis"):
        return step.text
    prior = _prior_completed_steps(job, step.id)
    if not prior:
        return step.text
    block = _format_prior_for_synthesis(prior)
    return (
        f"{step.text.strip()}\n\n---\n"
        "Données des étapes précédentes (à synthétiser en français, clair et actionnable) :\n"
        f"{block}"
    )


def _context_for_step(job: Job, step: JobStep) -> dict[str, Any]:
    ctx: dict[str, Any] = dict(job.base_context)
    
    # Injection de variables inter-étapes
    for s in job.steps:
        if s.id == step.id:
            break
        if s.status == "done" and isinstance(s.result, dict):
            v = s.result.get("variables")
            if not isinstance(v, dict):
                inner = s.result.get("result")
                if isinstance(inner, dict):
                    v = inner.get("variables")
            if isinstance(v, dict):
                for key, val in v.items():
                    ctx[key] = val

    ctx.update(step.context_patch)
    ctx["_trace_id"] = job.trace_id
    ctx["_job_id"] = job.id

    if ctx.get("_job_synthesis"):
        prior = _prior_completed_steps(job, step.id)
        if prior:
            ctx["_job_prior_results"] = prior
    if ctx.get("_capabilities_inventory"):
        ctx["_capabilities_catalog"] = _capabilities_catalog_payload()

    _inject_approval_tokens(job, step, ctx)

    # Élargissement contrôlé : on élève une action à effet de bord en exécution réelle
    # (injection du token + retrait du dry-run) seulement si la capability est allowlistée.
    if _is_elevated(job, step):
        approval_key, dry_flag = _APPROVAL_BY_ACTION_KEY[step.action_context_key]
        ctx[approval_key] = (job.stored_approval_token or "").strip() or _expected_token() or "job-preauthorized"
        ctx.pop(dry_flag, None)
    if step.attempts > 0:
        ctx["_job_retry"] = step.attempts
    return ctx


def advance_job(job_id: str) -> Job | None:
    """Fait avancer le job d'**une** étape (planification, exécution, retry, ou pause).

    Retourne l'état du job après l'opération, ou ``None`` s'il n'existe pas.
    Pur et synchrone : la boucle daemon ne fait qu'appeler cette fonction.
    """
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        if job.status in ("done", "failed", "cancelled", "waiting_approval"):
            return _clone(job)

        if job.status == "planning":
            job.status = "running" if job.steps else "done"
            if not job.steps:
                job.result_summary = "Aucune étape planifiable pour cet objectif."
            job.updated_ts = _now()
            _persist_locked(job)
            return _clone(job)

        # Trouver la prochaine étape actionnable.
        step = _next_actionable_step(job)
        if step is None:
            _finalize(job)
            job.updated_ts = _now()
            _persist_locked(job)
            return _clone(job)

        cap = capability_registry.get(step.capability)
        if cap is None:
            step.status = "failed"
            step.error = f"Capability inconnue : {step.capability}"
            _emit(job, "step_failed", step_id=step.id, capability=step.capability, error=step.error)
            _maybe_fail_job(job, step)
            job.updated_ts = _now()
            _persist_locked(job)
            return _clone(job)

        ctx = _context_for_step(job, step)
        policy = evaluate_action_policy(cap, ctx)
        step.policy = policy.model_dump()

        if not policy.allowed:
            # Action à risque non autorisée : on met le job en pause (pas d'action aveugle).
            step.status = "waiting_approval"
            job.status = "waiting_approval"
            _emit(
                job,
                "waiting_approval",
                step_id=step.id,
                capability=cap.name,
                decision=policy.decision,
                reason=policy.reason,
            )
            job.updated_ts = _now()
            _persist_locked(job)
            return _clone(job)

        # Exécution de l'étape.
        step.status = "running"
        step.attempts += 1
        _emit(
            job,
            "step_started",
            step_id=step.id,
            capability=cap.name,
            attempt=step.attempts,
            decision=policy.decision,
            real_execution=_is_elevated(job, step),
        )

    inventory_direct = bool(
        ctx.get("_capabilities_inventory") or step.context_patch.get("_capabilities_inventory")
    )
    dispatch_text = _dispatch_text_for_step(job, step, ctx) if not inventory_direct else step.text

    # Le dispatch peut être lent (LLM) : on le fait HORS verrou.
    try:
        if inventory_direct:
            result = _run_capabilities_inventory(network_devices=_network_devices_from_job(job))
        else:
            dispatch_actor = job.actor_id
            if step.capability == "core3_bot_action":
                override = ctx.get("_lia_job_actor")
                if isinstance(override, str) and override.strip():
                    dispatch_actor = override.strip()
            result = _dispatch(
                cap.routed_to, actor_id=dispatch_actor, text=dispatch_text, context=ctx
            )
    except Exception as e:  # pragma: no cover - dépend du handler
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    with _lock:
        # Le job a pu être annulé pendant le dispatch.
        live = _jobs.get(job_id)
        if live is None:
            return None
        if live.status == "cancelled":
            return _clone(live)
        # Retrouver l'étape (même id).
        live_step = next((s for s in live.steps if s.id == step.id), None)
        if live_step is None:
            return _clone(live)

        live_step.result = result if isinstance(result, dict) else {"payload": result}
        ok, reason = _evaluate_step(live_step, live_step.result if isinstance(live_step.result, dict) else {})
        if ok:
            live_step.status = "done"
            live_step.error = None
            _emit(live, "step_result", step_id=live_step.id, ok=True, attempt=live_step.attempts)
        else:
            live_step.error = reason or "Étape en échec."
            if live_step.attempts < live_step.max_attempts:
                # Auto-correction niveau étape : on re-tente (le contexte portera `_job_retry`).
                live_step.status = "queued"
                _emit(live, "step_retry", step_id=live_step.id, attempt=live_step.attempts, error=live_step.error)
            elif _maybe_replan(live, live_step):
                # Auto-correction niveau objectif : on a re-planifié, le job continue.
                live.updated_ts = _now()
                _persist_locked(live)
                return _clone(live)
            else:
                live_step.status = "failed"
                _emit(live, "step_failed", step_id=live_step.id, attempt=live_step.attempts, error=live_step.error)
                _maybe_fail_job(live, live_step)

        if live.status == "running" and _next_actionable_step(live) is None:
            _finalize(live)
        live.updated_ts = _now()
        _persist_locked(live)
        return _clone(live)


def _next_actionable_step(job: Job) -> JobStep | None:
    for st in job.steps:
        if st.status == "queued":
            return st
    return None


def _plan_signature(steps: list[JobStep]) -> tuple[tuple[str, str, str], ...]:
    """Signature comparable d'un plan (pour détecter un replan identique = pas de progrès)."""
    sig: list[tuple[str, str, str]] = []
    for s in steps:
        kind = ""
        if isinstance(s.action, dict) and isinstance(s.action.get("kind"), str):
            kind = s.action["kind"]
        sig.append((s.capability, (s.text or s.summary).strip().lower()[:120], kind))
    return tuple(sig)


def _maybe_replan(job: Job, step: JobStep) -> bool:
    """Re-planifie l'objectif après l'échec d'une étape (auto-correction Cowork).

    Borné par ``LBG_JOBS_MAX_REPLANS``. On n'effectue le replan que s'il produit un plan
    **différent** (sinon on évite une boucle stérile). Retourne True si un replan a eu lieu.
    """
    if continue_on_step_failure() or default_max_replans() <= 0:
        return False
    if job.replans >= default_max_replans():
        return False

    # Journaliser l'échec pour nourrir la re-planification (et la mémoire).
    job.error_log.append(
        {
            "step_id": step.id,
            "capability": step.capability,
            "summary": step.summary,
            "error": step.error,
            "attempts": step.attempts,
        }
    )

    memories = _recall_memories(job.objective)
    try:
        plan = svc_planner.plan_objective(
            job.objective, job.base_context, error_log=job.error_log, memories=memories or None
        )
    except Exception as e:  # pragma: no cover - robustesse planner
        _emit(job, "replan_failed", error=f"{type(e).__name__}: {e}")
        return False

    if not plan.steps:
        return False
    old_sig = _plan_signature(job.steps)
    new_steps = [_build_step({**s.as_dict(), "max_attempts": default_max_attempts()}) for s in plan.steps]
    if _plan_signature(new_steps) == old_sig:
        # Plan identique (typiquement planner déterministe) : pas de progrès possible.
        _emit(job, "replan_skipped", reason="plan identique", source=plan.source)
        return False

    job.replans += 1
    job.steps = new_steps
    job.cursor = 0
    job.plan_source = plan.source
    job.status = "running"
    _emit(
        job,
        "replanned",
        replan=job.replans,
        source=plan.source,
        n_steps=len(job.steps),
        after_error=step.error,
    )
    return True


def _record_job_experience(job: Job, *, outcome: str) -> None:
    try:
        problem = ""
        if job.error_log:
            last = job.error_log[-1]
            problem = f"{last.get('capability', '')}: {last.get('error', '')}"[:400]
        tags = [outcome]
        if job.plan_source:
            tags.append(job.plan_source)
        if job.replans:
            tags.append("replanned")
        svc_memory.record_experience(
            job.objective,
            outcome=outcome,
            problem=problem,
            resolution=(job.result_summary or "")[:400],
            tags=tags,
        )
    except Exception:
        return


def _maybe_fail_job(job: Job, step: JobStep) -> None:
    if continue_on_step_failure():
        # On laisse les étapes suivantes tenter leur chance.
        return
    job.status = "failed"
    job.result_summary = f"Échec à l'étape « {step.summary or step.capability} » : {step.error}"
    _emit(job, "failed", step_id=step.id, error=step.error)
    _record_job_experience(job, outcome="failed")


def _finalize(job: Job) -> None:
    if job.status in ("failed", "cancelled"):
        return
    failed = [s for s in job.steps if s.status == "failed"]
    done = [s for s in job.steps if s.status == "done"]
    if failed and not continue_on_step_failure():
        job.status = "failed"
        job.result_summary = f"{len(failed)} étape(s) en échec."
        _emit(job, "completed", status=job.status, summary=job.result_summary)
        _record_job_experience(job, outcome="failed")
        return
    job.status = "failed" if failed else "done"
    job.result_summary = (
        f"{len(done)}/{len(job.steps)} étape(s) réussie(s)."
        if not failed
        else f"{len(done)}/{len(job.steps)} réussie(s), {len(failed)} en échec."
    )
    _emit(job, "completed", status=job.status, summary=job.result_summary)
    _record_job_experience(job, outcome=("done" if job.status == "done" else "failed"))


def run_job_to_completion(job_id: str, *, max_steps: int = 64) -> Job | None:
    """Avance le job jusqu'à un état terminal ou ``waiting_approval`` (usage test/CLI)."""
    last: Job | None = None
    for _ in range(max(1, max_steps)):
        last = advance_job(job_id)
        if last is None:
            return None
        if last.status in ("done", "failed", "cancelled", "waiting_approval"):
            break
    return last


# --------------------------------------------------------------------------- #
# Thread daemon (production)
# --------------------------------------------------------------------------- #


def _pick_runnable_job_id() -> str | None:
    with _lock:
        for job in sorted(_jobs.values(), key=lambda j: j.created_ts):
            if job.status in ("running", "planning"):
                return job.id
    return None


def _loop() -> None:
    time.sleep(1.0)
    while not _stop.is_set():
        if runner_enabled():
            job_id = _pick_runnable_job_id()
            if job_id is not None:
                try:
                    advance_job(job_id)
                except Exception as e:  # pragma: no cover - robustesse daemon
                    print(json.dumps({"event": "orchestrator.jobs.loop_error", "error": f"{type(e).__name__}: {e}"}))
                # Enchaîner rapidement tant qu'il y a du travail.
                _stop.wait(timeout=0.05)
                continue
        _stop.wait(timeout=runner_interval_s())


def ensure_started() -> None:
    global _thread
    if _thread is not None:
        return
    _load_on_boot()
    _thread = threading.Thread(target=_loop, name="lbg-jobs", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
