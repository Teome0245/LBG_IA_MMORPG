from __future__ import annotations

import json
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from lbg_agents.dispatch import invoke_after_route


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def brain_enabled_default() -> bool:
    return _truthy(os.environ.get("LBG_BRAIN_ENABLED", "0"))


def brain_interval_s() -> int:
    raw = os.environ.get("LBG_BRAIN_INTERVAL_S", "30").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 30
    return max(5, min(n, 3600))


def brain_devops_autorestart_enabled() -> bool:
    return _truthy(os.environ.get("LBG_BRAIN_DEVOPS_AUTORESTART", "0"))


def brain_devops_approval() -> str:
    """
    Jeton d'approbation *pour le scheduler*.
    Si vide, le brain ne tentera jamais de `systemd_restart` en autonomie.
    """
    return os.environ.get("LBG_BRAIN_DEVOPS_APPROVAL", "").strip()


def brain_state_path() -> str:
    return os.environ.get("LBG_BRAIN_STATE_PATH", "/var/lib/lbg/brain/state.json").strip() or "/var/lib/lbg/brain/state.json"


def brain_max_actions_per_tick() -> int:
    raw = os.environ.get("LBG_BRAIN_MAX_ACTIONS_PER_TICK", "3").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 3
    return max(1, min(n, 20))


def brain_restart_cooldown_s() -> int:
    raw = os.environ.get("LBG_BRAIN_RESTART_COOLDOWN_S", "600").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 600
    return max(60, min(n, 86400))


def _clamp0100(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 100.0:
        return 100.0
    return x


def _now_ts() -> float:
    return float(time.time())


def _atomic_write_json(path: str, payload: dict[str, object]) -> str | None:
    """
    Best-effort persistance. Retourne une erreur (string) si échec, sinon None.
    """
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def _read_json(path: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return (raw if isinstance(raw, dict) else None, None)
    except FileNotFoundError:
        return (None, None)
    except Exception as e:
        return (None, f"{type(e).__name__}: {e}")


def _new_request_id() -> str:
    return uuid.uuid4().hex


def _desktop_healthz(base: str) -> dict[str, object]:
    b = base.strip().rstrip("/")
    if not b:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_DESKTOP_URL vide"}
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{b}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:300]}
        try:
            data = r.json()
        except Exception:
            data = {"payload": r.text[:300]}
        return {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@dataclass
class BrainState:
    enabled: bool
    interval_s: int
    gauges: dict[str, float]
    intent: str = "monitor"
    narrative: str = ""
    approval_requests: list[dict[str, object]] | None = None
    last_persist_error: str | None = None
    last_persist_ts: float | None = None
    last_restart_ts: float | None = None
    last_tick_ts: float | None = None
    last_tick_ok: bool | None = None
    last_error: str | None = None
    last_selfcheck: dict[str, object] | None = None
    last_desktop_healthz: dict[str, object] | None = None
    last_actions: list[dict[str, object]] | None = None


_lock = threading.Lock()
_state = BrainState(
    enabled=brain_enabled_default(),
    interval_s=brain_interval_s(),
    gauges={"confidence": 70.0, "stress": 20.0, "fatigue": 10.0, "curiosity": 25.0},
    intent="monitor",
    narrative="",
    approval_requests=[],
)
_thread: threading.Thread | None = None
_stop = threading.Event()


def get_state() -> BrainState:
    with _lock:
        return BrainState(**_state.__dict__)


def set_enabled(v: bool) -> BrainState:
    with _lock:
        _state.enabled = bool(v)
        _state.interval_s = brain_interval_s()
        st = BrainState(**_state.__dict__)
    return st


def _persist_state_locked() -> None:
    """
    À appeler uniquement sous `_lock`.
    """
    path = brain_state_path()
    payload: dict[str, object] = {
        "schema_version": 1,
        "enabled": bool(_state.enabled),
        "interval_s": int(_state.interval_s),
        "gauges": {k: float(v) for k, v in (_state.gauges or {}).items()},
        "intent": _state.intent,
        "narrative": _state.narrative,
        "approval_requests": list(_state.approval_requests or []),
        "last_restart_ts": _state.last_restart_ts,
        "last_tick_ts": _state.last_tick_ts,
        "ts": _now_ts(),
    }
    err = _atomic_write_json(path, payload)
    _state.last_persist_ts = _now_ts()
    _state.last_persist_error = err


def _load_state_on_boot() -> None:
    path = brain_state_path()
    raw, err = _read_json(path)
    with _lock:
        if err:
            _state.last_persist_error = err
            return
        if not raw:
            return
        gauges = raw.get("gauges")
        if isinstance(gauges, dict):
            for k in ("confidence", "stress", "fatigue", "curiosity"):
                v = gauges.get(k)
                if isinstance(v, (int, float)):
                    _state.gauges[k] = _clamp0100(float(v))
        apr = raw.get("approval_requests")
        if isinstance(apr, list):
            # conserve seulement les entrées dict
            _state.approval_requests = [a for a in apr if isinstance(a, dict)]
        intent = raw.get("intent")
        if isinstance(intent, str) and intent.strip():
            _state.intent = intent.strip()
        narrative = raw.get("narrative")
        if isinstance(narrative, str):
            _state.narrative = narrative
        lr = raw.get("last_restart_ts")
        if isinstance(lr, (int, float)):
            _state.last_restart_ts = float(lr)


def approve_request(request_id: str) -> BrainState:
    rid = (request_id or "").strip()
    if not rid:
        return get_state()
    with _lock:
        changed = False
        for r in _state.approval_requests or []:
            if not isinstance(r, dict):
                continue
            if r.get("id") == rid:
                r["approved"] = True
                r["approved_ts"] = _now_ts()
                changed = True
        if changed:
            _persist_state_locked()
        return BrainState(**_state.__dict__)


def _summarize_perception(*, devops: dict[str, Any] | None, desktop: dict[str, object] | None) -> tuple[bool, int, int]:
    """
    Retourne (overall_ok, n_bad_steps, n_unknown_steps).
    """
    overall_ok = True
    n_bad = 0
    n_unk = 0
    if isinstance(devops, dict):
        res = devops.get("result")
        if isinstance(res, dict):
            ok = res.get("ok")
            if ok is False:
                overall_ok = False
            steps = res.get("steps")
            if isinstance(steps, list):
                for s in steps:
                    if not isinstance(s, dict):
                        continue
                    h = s.get("healthy")
                    if h is True:
                        continue
                    if h is False:
                        overall_ok = False
                        n_bad += 1
                    else:
                        n_unk += 1
    if isinstance(desktop, dict):
        if desktop.get("skipped") is True:
            n_unk += 1
        elif desktop.get("ok") is False:
            overall_ok = False
            n_bad += 1
    return (overall_ok, n_bad, n_unk)


def _update_gauges_locked(*, overall_ok: bool, n_bad: int, n_unknown: int, did_actions: int) -> None:
    g = _state.gauges or {}
    conf = float(g.get("confidence", 70.0))
    stress = float(g.get("stress", 20.0))
    fatigue = float(g.get("fatigue", 10.0))
    curiosity = float(g.get("curiosity", 25.0))

    # Baseline drift
    stress -= 1.2
    fatigue -= 0.8
    curiosity -= 0.5
    if overall_ok:
        conf += 1.5
    else:
        conf -= 3.0 + 1.2 * float(n_bad)
        stress += 4.0 + 1.6 * float(n_bad)
        curiosity += 1.0 + 0.8 * float(n_unknown)

    # Uncertain signals increase curiosity slightly.
    if n_unknown > 0 and overall_ok:
        curiosity += 0.6 * float(n_unknown)

    # Actions cost fatigue.
    if did_actions > 0:
        fatigue += 2.5 * float(did_actions)
        stress += 0.5 * float(max(0, did_actions - 1))

    # Small noise to avoid "stuck" (bounded).
    conf += random.uniform(-0.2, 0.2)
    stress += random.uniform(-0.2, 0.2)

    g["confidence"] = _clamp0100(conf)
    g["stress"] = _clamp0100(stress)
    g["fatigue"] = _clamp0100(fatigue)
    g["curiosity"] = _clamp0100(curiosity)
    _state.gauges = g


def _pick_intent_locked(*, overall_ok: bool, n_bad: int, n_unknown: int) -> str:
    g = _state.gauges or {}
    conf = float(g.get("confidence", 70.0))
    stress = float(g.get("stress", 20.0))
    fatigue = float(g.get("fatigue", 10.0))
    curiosity = float(g.get("curiosity", 25.0))

    if n_bad > 0 and (stress > 45.0 or conf < 60.0):
        # If remediation possible but gated, we will request approval.
        return "request_approval" if brain_devops_autorestart_enabled() else "diagnose"
    if n_unknown > 0 and curiosity > 55.0 and fatigue < 80.0:
        return "diagnose"
    if overall_ok and fatigue < 85.0:
        return "monitor"
    return "monitor"


def _narrative_locked(*, overall_ok: bool, n_bad: int, n_unknown: int) -> str:
    g = _state.gauges or {}
    conf = int(round(float(g.get("confidence", 0.0))))
    stress = int(round(float(g.get("stress", 0.0))))
    fatigue = int(round(float(g.get("fatigue", 0.0))))
    curiosity = int(round(float(g.get("curiosity", 0.0))))
    if overall_ok:
        return f"État global stable. Confiance={conf}/100, stress={stress}/100, fatigue={fatigue}/100, curiosité={curiosity}/100."
    parts = []
    if n_bad:
        parts.append(f"{n_bad} signal(s) non sain(s)")
    if n_unknown:
        parts.append(f"{n_unknown} inconnu(s)/skipped")
    why = ", ".join(parts) if parts else "signal(s) dégradé(s)"
    return f"Je détecte {why}. Confiance={conf}/100, stress={stress}/100, fatigue={fatigue}/100, curiosité={curiosity}/100."


def _tick_once() -> None:
    trace_id = uuid.uuid4().hex
    t0 = time.time()
    actions: list[dict[str, object]] = []
    ok = True
    err: str | None = None
    selfcheck_out: dict[str, object] | None = None
    desktop_out: dict[str, object] | None = None
    did_actions = 0

    try:
        # 1) DevOps selfcheck (safe) — dry-run par défaut en autonomie
        devops_ctx: dict[str, Any] = {
            "_trace_id": trace_id,
            "devops_action": {"kind": "selfcheck"},
            "devops_selfcheck": True,
            "devops_dry_run": True,
        }
        devops = invoke_after_route(
            "agent.devops",
            actor_id="svc:brain",
            text="brain selfcheck",
            context=devops_ctx,
        )
        selfcheck_out = devops
        actions.append({"kind": "devops_selfcheck", "dry_run": True, "ok": bool(devops.get("result", {}).get("ok"))})
        did_actions += 1

        # 2) Desktop healthz (safe) — ping direct du worker
        desktop_base = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip()
        if desktop_base:
            desktop_out = _desktop_healthz(desktop_base)
            actions.append({"kind": "desktop_healthz", "ok": bool(desktop_out.get("ok"))})
            did_actions += 1
        else:
            desktop_out = {"ok": False, "skipped": True, "detail": "LBG_AGENT_DESKTOP_URL non défini"}

        # 3) Autorestart systemd sous approval (opt-in)
        if brain_devops_autorestart_enabled():
            token = brain_devops_approval()
            res = devops.get("result") if isinstance(devops, dict) else None
            steps = (res or {}).get("steps") if isinstance(res, dict) else None
            # Heuristique v1 : si une unité est unhealthy -> demander approbation, puis redémarrer (cooldown + 1 par tick).
            target_unit: str | None = None
            if isinstance(steps, list):
                for s in steps:
                    if not isinstance(s, dict):
                        continue
                    if s.get("kind") != "systemd_is_active":
                        continue
                    if s.get("healthy") is True:
                        continue
                    unit = s.get("unit")
                    if isinstance(unit, str) and unit.strip():
                        target_unit = unit.strip()
                        break

            if target_unit:
                with _lock:
                    # crée une demande si aucune demande non traitée existe déjà
                    existing = False
                    for r in _state.approval_requests or []:
                        if not isinstance(r, dict):
                            continue
                        if r.get("unit") == target_unit and r.get("done") is not True:
                            existing = True
                    if not existing:
                        _state.approval_requests = list(_state.approval_requests or [])
                        _state.approval_requests.append(
                            {
                                "id": _new_request_id(),
                                "kind": "systemd_restart",
                                "unit": target_unit,
                                "reason": "selfcheck détecte l'unité non saine",
                                "created_ts": _now_ts(),
                                "approved": False,
                                "done": False,
                            }
                        )

                    # exécution : uniquement si token présent + demande approuvée + cooldown ok
                    cooldown_ok = True
                    if isinstance(_state.last_restart_ts, (int, float)) and _state.last_restart_ts:
                        cooldown_ok = (_now_ts() - float(_state.last_restart_ts)) >= float(brain_restart_cooldown_s())

                    approved_id: str | None = None
                    if token and cooldown_ok:
                        for r in _state.approval_requests or []:
                            if not isinstance(r, dict):
                                continue
                            if r.get("unit") == target_unit and r.get("kind") == "systemd_restart" and r.get("done") is not True:
                                if r.get("approved") is True:
                                    approved_id = str(r.get("id") or "")
                                    break

                if not token:
                    actions.append({"kind": "systemd_restart", "unit": target_unit, "skipped": True, "reason": "missing LBG_BRAIN_DEVOPS_APPROVAL"})
                elif approved_id and did_actions < brain_max_actions_per_tick():
                    restart_ctx: dict[str, Any] = {
                        "_trace_id": trace_id,
                        "devops_action": {"kind": "systemd_restart", "unit": target_unit},
                        "devops_dry_run": False,
                        "devops_approval": token,
                    }
                    r2 = invoke_after_route(
                        "agent.devops",
                        actor_id="svc:brain",
                        text=f"brain restart {target_unit}",
                        context=restart_ctx,
                    )
                    actions.append({"kind": "systemd_restart", "unit": target_unit, "ok": bool(r2.get("ok")), "approved_id": approved_id})
                    did_actions += 1
                    with _lock:
                        _state.last_restart_ts = _now_ts()
                        # marque la demande comme done (consommée)
                        for r in _state.approval_requests or []:
                            if isinstance(r, dict) and r.get("id") == approved_id:
                                r["done"] = True
                                r["done_ts"] = _now_ts()
                                r["result_ok"] = bool(r2.get("ok"))
                else:
                    if token and not approved_id:
                        actions.append({"kind": "systemd_restart", "unit": target_unit, "skipped": True, "reason": "awaiting_approval"})
                    elif token and not cooldown_ok:
                        actions.append({"kind": "systemd_restart", "unit": target_unit, "skipped": True, "reason": "cooldown"})
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}"

    overall_ok, n_bad, n_unknown = _summarize_perception(devops=selfcheck_out, desktop=desktop_out)
    with _lock:
        _update_gauges_locked(overall_ok=overall_ok, n_bad=n_bad, n_unknown=n_unknown, did_actions=did_actions)
        _state.intent = _pick_intent_locked(overall_ok=overall_ok, n_bad=n_bad, n_unknown=n_unknown)
        _state.narrative = _narrative_locked(overall_ok=overall_ok, n_bad=n_bad, n_unknown=n_unknown)

    elapsed_ms = int((time.time() - t0) * 1000)
    print(
        json.dumps(
            {
                "event": "orchestrator.brain.tick",
                "trace_id": trace_id,
                "ok": ok,
                "elapsed_ms": elapsed_ms,
                "actions": actions,
                "intent": _state.intent,
            },
            ensure_ascii=False,
        )
    )

    with _lock:
        _state.last_tick_ts = time.time()
        _state.last_tick_ok = ok
        _state.last_error = err
        _state.last_actions = actions
        _state.last_selfcheck = selfcheck_out
        _state.last_desktop_healthz = desktop_out
        _persist_state_locked()


def _loop() -> None:
    # Petit délai pour laisser uvicorn monter.
    time.sleep(1.0)
    while not _stop.is_set():
        st = get_state()
        if st.enabled:
            _tick_once()
        _stop.wait(timeout=float(st.interval_s))


def ensure_started() -> None:
    global _thread
    if _thread is not None:
        return
    _load_state_on_boot()
    _thread = threading.Thread(target=_loop, name="lbg-brain", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()

