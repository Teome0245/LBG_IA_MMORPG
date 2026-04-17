"""
Pont optionnel vers `mmo_server.lyra_engine.gauges` (même venv que `install_local.sh`).

Si `lyra_engine` n’est pas importable (paquet `mmo_server` non installé), aucun pas de simulation
n’est appliqué — l’echo brut de `context.lyra` reste le comportement par défaut.
"""

from __future__ import annotations

from typing import Any


def step_lyra_gauges_if_applicable(lyra: dict[str, Any]) -> dict[str, Any] | None:
    """
    Si `lyra` contient `gauges` avec au moins une clé hunger/thirst/fatigue, applique
    `GaugesState.step(dt_s)` et renvoie un nouvel objet `lyra` enrichi.

    `dt_s` : secondes simulées (défaut 60), borné à [0, 86400].
    """
    try:
        from lyra_engine.gauges import GaugesState
    except ImportError:
        return None

    raw = lyra.get("gauges")
    if not isinstance(raw, dict):
        return None
    keys = ("hunger", "thirst", "fatigue")
    if not any(k in raw for k in keys):
        return None

    def _f(v: Any) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return 0.0
        return float(v)

    state = GaugesState(
        hunger=_f(raw.get("hunger")),
        thirst=_f(raw.get("thirst")),
        fatigue=_f(raw.get("fatigue")),
    )
    dt_raw = lyra.get("dt_s", 60.0)
    try:
        dt_s = float(dt_raw)
    except (TypeError, ValueError):
        dt_s = 60.0
    dt_s = max(0.0, min(86400.0, dt_s))
    state.step(dt_s)

    out: dict[str, Any] = dict(lyra)
    out["gauges"] = {
        "hunger": state.hunger,
        "thirst": state.thirst,
        "fatigue": state.fatigue,
    }
    prev_meta = lyra.get("meta")
    meta: dict[str, Any] = dict(prev_meta) if isinstance(prev_meta, dict) else {}
    meta["lyra_engine"] = "gauges.step"
    meta["dt_s"] = dt_s
    out["meta"] = meta
    return out


def step_context_lyra_once(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Applique au plus un pas de jauges sur ``context["lyra"]`` si applicable.

    Retourne ``(contexte_pour_agents, lyra_pour_output)``.
    Sans ``lyra`` objet : ``(context, None)``.
    """
    if not isinstance(context, dict):
        return context, None
    lyra = context.get("lyra")
    if not isinstance(lyra, dict):
        return context, None
    meta = lyra.get("meta")
    if isinstance(meta, dict) and meta.get("source") == "mmo_world":
        # État déjà avancé par le tick `mmo_server` : ne pas appliquer un second `step` ici.
        c = dict(context)
        return c, lyra
    stepped = step_lyra_gauges_if_applicable(lyra)
    lyra_out = stepped if stepped is not None else lyra
    if stepped is not None:
        c = dict(context)
        c["lyra"] = stepped
        return c, lyra_out
    return context, lyra_out
