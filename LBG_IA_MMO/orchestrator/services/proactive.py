"""
Couche proactive : greffe ``hybrid_proactive_agent`` + daemon optionnel.

- Enrichit ``POST /v1/route`` avec ``proactive_hints`` / ``proactive_action``.
- Boucle daemon (opt-in) : ``tick_silence`` → initiative → job autonome read-only si autorisé.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from hybrid_proactive_agent import HybridProactiveEngine, integration_hints
from hybrid_proactive_agent.engine import ActionKind, ProactiveAction

from services import jobs as svc_jobs
from services.lia_jobs import LIA_ACTOR_ID, lia_core3_context_patch, lia_tick_prompt_from_objective

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def proactive_enabled() -> bool:
    return _truthy(os.environ.get("LBG_PROACTIVE_ENABLED", "0"))


def proactive_interval_s() -> float:
    try:
        return max(30.0, float(os.environ.get("LBG_PROACTIVE_INTERVAL_S", "300").strip()))
    except ValueError:
        return 300.0


def proactive_auto_jobs() -> bool:
    return _truthy(os.environ.get("LBG_PROACTIVE_AUTO_JOBS", "1"))


def proactive_route_hints() -> bool:
    return _truthy(os.environ.get("LBG_PROACTIVE_ROUTE_HINTS", "1"))


def proactive_actor_id() -> str:
    return os.environ.get("LBG_PROACTIVE_ACTOR_ID", "system:proactive").strip() or "system:proactive"


def proactive_min_job_interval_s() -> float:
    try:
        return max(60.0, float(os.environ.get("LBG_PROACTIVE_MIN_JOB_INTERVAL_S", "900").strip()))
    except ValueError:
        return 900.0


def proactive_state_path() -> str:
    return os.environ.get("LBG_PROACTIVE_STATE_PATH", "/var/lib/lbg/proactive/state.json").strip()


def proactive_tension_job_threshold() -> float:
    try:
        return max(0.3, min(1.0, float(os.environ.get("LBG_PROACTIVE_TENSION_JOB_THRESHOLD", "0.55").strip())))
    except ValueError:
        return 0.55


def _default_objective() -> str:
    return os.environ.get(
        "LBG_PROACTIVE_DEFAULT_OBJECTIVE",
        "Analyse proactive de l'environnement réseau et de l'infra (instantané T, read-only).",
    ).strip()


def proactive_lia_jobs_enabled() -> bool:
    return _truthy(os.environ.get("LBG_PROACTIVE_LIA_JOBS", "0"))


def _lia_default_objective() -> str:
    return os.environ.get(
        "LBG_PROACTIVE_LIA_OBJECTIVE",
        "Tour proactif Lia en MMO — incarnation orchestrateur, une action en jeu (observe et agis).",
    ).strip()


def _lia_autonomy_thread_active() -> bool:
    try:
        from lbg_agents.lia_autonomy import lia_autonomy_enabled

        return lia_autonomy_enabled()
    except ImportError:
        return False


# --------------------------------------------------------------------------- #
# État moteur + persistance best-effort
# --------------------------------------------------------------------------- #


@dataclass
class ProactiveRuntime:
    engine: HybridProactiveEngine = field(default_factory=HybridProactiveEngine)
    last_user_ts: float = field(default_factory=time.time)
    last_auto_job_ts: float = 0.0
    last_tick_ts: float = field(default_factory=time.time)
    ticks: int = 0
    auto_jobs_spawned: int = 0
    last_action: dict[str, Any] | None = None
    last_job_id: str | None = None


_lock = threading.Lock()
_runtime = ProactiveRuntime()
_stop = threading.Event()
_thread: threading.Thread | None = None


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except OSError:
        pass


def _load_state() -> None:
    path = proactive_state_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    with _lock:
        try:
            _runtime.engine.state = _runtime.engine.state.model_validate(raw.get("engine_state") or {})
        except Exception:
            pass
        _runtime.last_auto_job_ts = float(raw.get("last_auto_job_ts") or 0.0)
        _runtime.auto_jobs_spawned = int(raw.get("auto_jobs_spawned") or 0)
        _runtime.last_job_id = raw.get("last_job_id") if isinstance(raw.get("last_job_id"), str) else None


def _persist_state() -> None:
    with _lock:
        payload = {
            "engine_state": _runtime.engine.state.model_dump(),
            "last_auto_job_ts": _runtime.last_auto_job_ts,
            "auto_jobs_spawned": _runtime.auto_jobs_spawned,
            "last_job_id": _runtime.last_job_id,
            "saved_ts": time.time(),
        }
    _atomic_write_json(proactive_state_path(), payload)


def _tcp_open(host: str, port: int, timeout_s: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _mmo_sidecar_host() -> str:
    raw = os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "").strip()
    if raw and "//" in raw:
        host_port = raw.split("//", 1)[1].split("/", 1)[0]
        return host_port.split(":")[0] or "192.168.0.245"
    return os.environ.get("LBG_LAN_HOST_MMO", "192.168.0.245").split(":")[0]


def _mmo_signals() -> dict[str, Any]:
    mmo_host = _mmo_sidecar_host()
    sidecar_ok = _tcp_open(mmo_host, 8791)
    return {
        "mmo_host": mmo_host,
        "mmo_sidecar_reachable": sidecar_ok,
    }


def _infra_signals() -> dict[str, Any]:
    """Signaux légers pour le moteur (pas de scan complet à chaque tick)."""
    core_host = os.environ.get("LBG_LAN_HOST_CORE", "192.168.0.140").split(":")[0]
    ad_url = os.environ.get("AGENT_WINDOWS_SRV_AD_URL", "http://192.168.0.100:5005")
    ad_host = ad_url.split("//")[-1].split(":")[0] if "//" in ad_url else "192.168.0.100"
    orch_ok = _tcp_open(core_host, 8010)
    ad_agent_ok = _tcp_open(ad_host, 5005)
    signals: dict[str, Any] = {
        "orchestrator_reachable": orch_ok,
        "ad_agent_reachable": ad_agent_ok,
    }
    signals.update(_mmo_signals())
    if not orch_ok:
        signals["missing_info"] = True
        signals["objectif_flou"] = True
    if not ad_agent_ok:
        signals["ad_agent_down"] = True
    if signals.get("mmo_sidecar_reachable"):
        signals["lia_mmo_available"] = True
    return signals


def _build_decide_context(intent: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "intent": intent or "",
        "objectif": "surveillance proactive LAN/infra",
        "contraintes": "read-only, dry-run, pas d'effet de bord sans token",
    }
    ctx.update(_infra_signals())
    if isinstance(extra, dict):
        ctx.update(extra)
    return ctx


def observe_turn(
    *,
    actor_id: str,
    text: str,
    intent: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Appelé après un tour utilisateur (route). Retourne hints + action optionnelle."""
    if not proactive_enabled():
        return {}
    ctx = context if isinstance(context, dict) else {}
    decide_ctx = _build_decide_context(
        intent,
        {
            "objectif": text[:500] if text else ctx.get("objectif"),
            "actor_id": actor_id,
            "missing_info": not intent or intent == "unknown",
        },
    )
    with _lock:
        _runtime.engine.observe_user_turn(text, decide_ctx)
        action = _runtime.engine.decide(decide_ctx)
        hints = integration_hints(_runtime.engine.state, {"session_id": actor_id})
        _runtime.last_user_ts = time.time()
        _runtime.last_action = action.model_dump()
    _persist_state()
    out: dict[str, Any] = {"hints": hints, "action": _runtime.last_action}
    return out


def enrich_route_output(
    *,
    actor_id: str,
    text: str,
    intent: str,
    context: dict[str, Any] | None,
    out_body: dict[str, Any],
) -> None:
    if not proactive_enabled() or not proactive_route_hints():
        return
    rec = observe_turn(actor_id=actor_id, text=text, intent=intent, context=context)
    if not rec:
        return
    hints = rec.get("hints")
    if isinstance(hints, dict):
        out_body["proactive_hints"] = hints
    action = rec.get("action")
    if isinstance(action, dict) and action.get("message"):
        out_body["proactive_action"] = action


def _should_spawn_job(action: ProactiveAction) -> bool:
    if not proactive_auto_jobs() or not svc_jobs.runner_enabled():
        return False
    if action.mode != "autonome" and action.kind not in (ActionKind.autonomous_nudge, ActionKind.plan):
        return False
    with _lock:
        if time.time() - _runtime.last_auto_job_ts < proactive_min_job_interval_s():
            return False
        if _runtime.engine.state.tension < proactive_tension_job_threshold():
            return False
        # Pas de job proactive si un job système tourne déjà
        active_ids = {proactive_actor_id(), LIA_ACTOR_ID}
        for aid in active_ids:
            for job in svc_jobs.list_jobs(actor_id=aid)[:8]:
                if job.status in ("running", "planning", "waiting_approval", "queued"):
                    return False
    return True


def _pick_proactive_objective(action: ProactiveAction) -> tuple[str, str, dict[str, Any]]:
    """Retourne (objectif, actor_id job, contexte base)."""
    infra_objective = _default_objective()
    if action.kind == ActionKind.plan:
        infra_objective = (
            "Auto checkup infrastructure LBG et cartographie réseau LAN (read-only, instantané T)."
        )
    ctx: dict[str, Any] = {
        "_trace_id": f"proactive-{uuid.uuid4().hex[:12]}",
        "_proactive_spawn": True,
        "devops_dry_run": True,
    }
    actor = proactive_actor_id()

    use_lia = (
        proactive_lia_jobs_enabled()
        and not _lia_autonomy_thread_active()
        and _mmo_signals().get("mmo_sidecar_reachable")
    )
    if use_lia:
        with _lock:
            use_lia = _runtime.auto_jobs_spawned % 2 == 1
    if use_lia:
        prompt = lia_tick_prompt_from_objective(_lia_default_objective())
        ctx.update(lia_core3_context_patch(prompt=prompt))
        ctx["_lia_job_actor"] = LIA_ACTOR_ID
        ctx["_proactive_lia_tick"] = True
        return _lia_default_objective(), LIA_ACTOR_ID, ctx

    return infra_objective, actor, ctx


def _spawn_proactive_job(action: ProactiveAction) -> str | None:
    objective, actor, ctx = _pick_proactive_objective(action)
    job = svc_jobs.create_job(
        actor_id=actor,
        objective=objective,
        context=ctx,
        auto_start=True,
    )
    with _lock:
        _runtime.last_auto_job_ts = time.time()
        _runtime.auto_jobs_spawned += 1
        _runtime.last_job_id = job.id
        _runtime.engine.cooldown_decay()
    _persist_state()
    print(
        json.dumps(
            {
                "event": "orchestrator.proactive.job_spawned",
                "job_id": job.id,
                "objective": objective[:200],
                "action_kind": action.kind.value,
                "mode": action.mode,
            },
            ensure_ascii=False,
        )
    )
    return job.id


def _tick_once() -> None:
    if not proactive_enabled():
        return
    interval = proactive_interval_s()
    with _lock:
        now = time.time()
        dt = max(0.0, now - _runtime.last_tick_ts)
        _runtime.last_tick_ts = now
        _runtime.ticks += 1
        _runtime.engine.tick_silence(dt if dt > 0 else interval)
        decide_ctx = _build_decide_context()
        action = _runtime.engine.decide(decide_ctx)
        _runtime.last_action = action.model_dump()

    spawned: str | None = None
    if _should_spawn_job(action):
        spawned = _spawn_proactive_job(action)

    if spawned is None:
        _persist_state()

    print(
        json.dumps(
            {
                "event": "orchestrator.proactive.tick",
                "ticks": _runtime.ticks,
                "mode": action.mode,
                "kind": action.kind.value,
                "tension": round(_runtime.engine.state.tension, 3),
                "spawned_job": spawned,
            },
            ensure_ascii=False,
        )
    )


def _loop() -> None:
    time.sleep(2.0)
    while not _stop.is_set():
        try:
            _tick_once()
        except Exception as e:  # pragma: no cover
            print(json.dumps({"event": "orchestrator.proactive.loop_error", "error": f"{type(e).__name__}: {e}"}))
        _stop.wait(timeout=proactive_interval_s())


def get_status() -> dict[str, Any]:
    with _lock:
        st = _runtime.engine.state
        return {
            "enabled": proactive_enabled(),
            "auto_jobs": proactive_auto_jobs() and svc_jobs.runner_enabled(),
            "interval_s": proactive_interval_s(),
            "ticks": _runtime.ticks,
            "mode": st.mode,
            "tension": round(st.tension, 3),
            "curiosite": round(st.curiosite, 3),
            "silence_seconds_est": round(st.silence_seconds_est, 1),
            "auto_jobs_spawned": _runtime.auto_jobs_spawned,
            "last_job_id": _runtime.last_job_id,
            "last_action": _runtime.last_action,
            "lia_jobs": proactive_lia_jobs_enabled() and not _lia_autonomy_thread_active(),
            "lia_autonomy_thread": _lia_autonomy_thread_active(),
            "infra_signals": _infra_signals(),
        }


def ensure_started() -> None:
    global _thread
    if _thread is not None:
        return
    if not proactive_enabled():
        return
    _load_state()
    _thread = threading.Thread(target=_loop, name="lbg-proactive", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    _persist_state()
