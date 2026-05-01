"""
Couplage optionnel Brain -> Lyra (influence faible, safe).

Ce module lit les jauges du Brain orchestrateur et applique une influence bornée
sur ``context.lyra`` avant routage.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return _truthy(os.environ.get("LBG_BRAIN_LYRA_BRIDGE_ENABLED", "0"))


def _scale_world() -> float:
    raw = os.environ.get("LBG_BRAIN_LYRA_WORLD_SCALE", "0.03").strip()
    try:
        n = float(raw)
    except ValueError:
        n = 0.03
    return max(0.0, min(n, 0.25))


def _scale_assistant() -> float:
    raw = os.environ.get("LBG_BRAIN_LYRA_ASSISTANT_SCALE", "5.0").strip()
    try:
        n = float(raw)
    except ValueError:
        n = 5.0
    return max(0.0, min(n, 25.0))


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
    return bool(meta.get("skip_brain_bridge"))


async def _fetch_brain_status() -> dict[str, Any] | None:
    base = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").strip().rstrip("/")
    if not base:
        return None
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{base}/v1/brain/status")
        if r.status_code != 200:
            logger.info("brain->lyra bridge: orchestrator status HTTP %s", r.status_code)
            return None
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.info("brain->lyra bridge: fetch failed: %s", e)
        return None


def _influence_from_brain(brain: dict[str, Any]) -> tuple[float, float]:
    gauges = brain.get("gauges")
    if not isinstance(gauges, dict):
        return (0.0, 0.0)
    stress = _clamp0100(float(gauges.get("stress", 0.0)))
    conf = _clamp0100(float(gauges.get("confidence", 50.0)))
    # positive means "more pressure", negative means "calmer"
    pressure = ((stress - 50.0) / 50.0 + (50.0 - conf) / 50.0) / 2.0
    # confidence axis used for assistant confidence direct nudging
    conf_axis = (conf - 50.0) / 50.0
    return (max(-1.0, min(1.0, pressure)), max(-1.0, min(1.0, conf_axis)))


def _apply_world(lyra: dict[str, Any], pressure: float) -> None:
    gauges = lyra.get("gauges")
    if not isinstance(gauges, dict):
        return
    k = _scale_world()
    delta = pressure * k
    for key in ("hunger", "thirst", "fatigue"):
        try:
            cur = float(gauges.get(key, 0.0))
        except Exception:
            cur = 0.0
        gauges[key] = _clamp01(cur + delta)


def _apply_assistant(lyra: dict[str, Any], pressure: float, conf_axis: float) -> None:
    gauges = lyra.get("gauges")
    if not isinstance(gauges, dict):
        return
    k = _scale_assistant()
    # stress/pressure reduces patience & energy a bit
    for key in ("patience", "energie"):
        try:
            cur = float(gauges.get(key, 0.0))
        except Exception:
            cur = 0.0
        gauges[key] = _clamp0100(cur - (pressure * k))
    # confidence axis nudges confidence/chaleur positively if high confidence
    for key in ("confiance", "chaleur"):
        try:
            cur = float(gauges.get(key, 0.0))
        except Exception:
            cur = 0.0
        gauges[key] = _clamp0100(cur + (conf_axis * k))


async def merge_brain_lyra_if_configured(context: dict[str, Any]) -> None:
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

    brain = await _fetch_brain_status()
    if not brain:
        return
    pressure, conf_axis = _influence_from_brain(brain)
    if kind == "assistant":
        _apply_assistant(lyra, pressure, conf_axis)
    else:
        _apply_world(lyra, pressure)

    meta = lyra.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["brain_bridge"] = {
        "enabled": True,
        "pressure": round(pressure, 4),
        "confidence_axis": round(conf_axis, 4),
        "source": "orchestrator_brain",
    }
    lyra["meta"] = meta
    context["lyra"] = lyra

