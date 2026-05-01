"""
Régulation Lyra safe (aucune action infra destructive).

Objectif: éviter la dérive des jauges en appliquant une micro-action bornée
à chaque appel (max 1 action, avec cooldown).
"""

from __future__ import annotations

import os
import time
from typing import Any


_last_action_ts: float = 0.0


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return _truthy(os.environ.get("LBG_LYRA_REGULATOR_ENABLED", "1"))


def _cooldown_s() -> int:
    raw = os.environ.get("LBG_LYRA_REGULATOR_COOLDOWN_S", "60").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 60
    return max(0, min(n, 3600))


def _world_warning() -> float:
    raw = os.environ.get("LBG_LYRA_REGULATOR_WORLD_WARNING", "0.55").strip()
    try:
        n = float(raw)
    except ValueError:
        n = 0.55
    return max(0.0, min(n, 1.0))


def _world_critical() -> float:
    raw = os.environ.get("LBG_LYRA_REGULATOR_WORLD_CRITICAL", "0.75").strip()
    try:
        n = float(raw)
    except ValueError:
        n = 0.75
    return max(0.0, min(n, 1.0))


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _clamp0100(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 100.0:
        return 100.0
    return x


def _skip(context: dict[str, Any]) -> bool:
    lyra = context.get("lyra")
    if not isinstance(lyra, dict):
        return False
    meta = lyra.get("meta")
    if not isinstance(meta, dict):
        return False
    return bool(meta.get("skip_regulation"))


def _append_meta(lyra: dict[str, Any], event: dict[str, Any]) -> None:
    meta = lyra.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["lyra_regulation"] = event
    lyra["meta"] = meta


def _regulate_world(lyra: dict[str, Any]) -> dict[str, Any]:
    gauges = lyra.get("gauges")
    if not isinstance(gauges, dict):
        return {"applied": False, "reason": "missing_gauges"}
    hunger = _clamp01(float(gauges.get("hunger", 0.0)))
    thirst = _clamp01(float(gauges.get("thirst", 0.0)))
    fatigue = _clamp01(float(gauges.get("fatigue", 0.0)))
    warning = _world_warning()
    critical = _world_critical()
    ranked = sorted(
        [("hunger", hunger), ("thirst", thirst), ("fatigue", fatigue)],
        key=lambda x: x[1],
        reverse=True,
    )
    top_k, top_v = ranked[0]
    if top_v < warning:
        return {"applied": False, "reason": "stable", "top": {top_k: round(top_v, 4)}}

    # Action safe: réduire le besoin dominant.
    delta = 0.10 if top_v >= critical else 0.06
    gauges[top_k] = _clamp01(float(gauges.get(top_k, 0.0)) - delta)
    return {
        "applied": True,
        "mode": "world",
        "action": f"reduce_{top_k}",
        "severity": "critical" if top_v >= critical else "warning",
        "delta": round(delta, 4),
        "before": {top_k: round(top_v, 4)},
        "after": {top_k: round(float(gauges[top_k]), 4)},
    }


def _regulate_assistant(lyra: dict[str, Any]) -> dict[str, Any]:
    gauges = lyra.get("gauges")
    if not isinstance(gauges, dict):
        return {"applied": False, "reason": "missing_gauges"}
    energie = _clamp0100(float(gauges.get("energie", 60.0)))
    patience = _clamp0100(float(gauges.get("patience", 60.0)))
    confiance = _clamp0100(float(gauges.get("confiance", 60.0)))
    # priorité: restaurer l'énergie, puis patience, puis confiance
    if energie < 50.0:
        d = 10.0 if energie < 35.0 else 6.0
        gauges["energie"] = _clamp0100(energie + d)
        return {"applied": True, "mode": "assistant", "action": "recover_energy", "delta": d}
    if patience < 50.0:
        d = 8.0 if patience < 35.0 else 5.0
        gauges["patience"] = _clamp0100(patience + d)
        return {"applied": True, "mode": "assistant", "action": "restore_patience", "delta": d}
    if confiance < 50.0:
        d = 6.0 if confiance < 35.0 else 4.0
        gauges["confiance"] = _clamp0100(confiance + d)
        return {"applied": True, "mode": "assistant", "action": "restore_confidence", "delta": d}
    return {"applied": False, "reason": "stable"}


async def regulate_lyra_if_configured(context: dict[str, Any]) -> None:
    global _last_action_ts
    if not _enabled():
        return
    if _skip(context):
        return
    lyra = context.get("lyra")
    if not isinstance(lyra, dict):
        return
    kind = lyra.get("kind")
    if not isinstance(kind, str):
        return

    now = time.time()
    cd = float(_cooldown_s())
    if cd > 0 and (now - _last_action_ts) < cd:
        _append_meta(
            lyra,
            {"applied": False, "reason": "cooldown", "cooldown_s": int(cd), "remaining_s": int(max(0.0, cd - (now - _last_action_ts)))},
        )
        context["lyra"] = lyra
        return

    if kind == "assistant":
        ev = _regulate_assistant(lyra)
    else:
        ev = _regulate_world(lyra)

    if ev.get("applied") is True:
        _last_action_ts = now
    _append_meta(lyra, ev)
    context["lyra"] = lyra

