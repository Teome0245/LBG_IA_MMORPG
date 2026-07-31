"""Audit Ollama dual-host — heavy 110 + light 111 vs config LBG."""

from __future__ import annotations

import os
from typing import Any

import httpx

# Rôles REASON dont le modèle doit être présent sur le nœud light (111).
_LIGHT_ROLES = frozenset({"reason_router", "reason_json", "reason_fast"})


def ollama_base_url() -> str:
    """Nœud heavy (110) — défaut historique."""
    return (
        os.environ.get("LBG_TEAM_OPS_OLLAMA_URL", "").strip()
        or os.environ.get("LBG_REASON_HEAVY_BASE_URL", "").strip()
        or os.environ.get("LBG_REASON_LOCAL_BASE_URL", "").strip()
        or os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.110:11434").strip()
    ).rstrip("/")


def light_ollama_base_url() -> str:
    return (
        os.environ.get("LBG_REASON_LIGHT_BASE_URL", "").strip()
        or os.environ.get("LBG_REASON_ROUTER_BASE_URL", "").strip()
        or os.environ.get("LBG_REASON_JSON_BASE_URL", "").strip()
        or "http://192.168.0.111:11434"
    ).rstrip("/")


def _ollama_host_hint() -> str:
    base = ollama_base_url().lower()
    if "11434" in base or "ollama" in base:
        return base
    return "192.168.0.110:11434"


def _base_url_for_role(role: str) -> str:
    """URL associée au rôle (light 111 pour router/json, sinon heavy 110)."""
    light = light_ollama_base_url()
    if role in _LIGHT_ROLES and light:
        return light
    mapping = {
        "dialogue_local": "LBG_DIALOGUE_LLM_BASE_URL",
        "dialogue_fast": "LBG_DIALOGUE_FAST_BASE_URL",
        "reason_default": "LBG_REASON_LOCAL_BASE_URL",
        "reason_forge": "LBG_REASON_LOCAL_BASE_URL",
        "reason_router": "LBG_REASON_LIGHT_BASE_URL",
        "reason_json": "LBG_REASON_LIGHT_BASE_URL",
        "reason_fast": "LBG_REASON_LIGHT_BASE_URL",
        "reason_code": "LBG_REASON_LOCAL_BASE_URL",
        "reason_pm": "LBG_REASON_LOCAL_BASE_URL",
        "jobs_planner": "LBG_JOBS_PLANNER_LLM_BASE_URL",
        "companion": "LBG_COMPANION_LLM_BASE_URL",
    }
    key = mapping.get(role, "")
    if not key:
        return ollama_base_url()
    raw = os.environ.get(key, "").strip()
    if role in _LIGHT_ROLES:
        return (raw or light or ollama_base_url()).rstrip("/")
    return (raw or ollama_base_url()).rstrip("/")


def _is_local_ollama_base(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return True
    if ":11434" in u:
        return True
    return any(h in u for h in ("192.168.0.110", "192.168.0.111", "127.0.0.1", "localhost"))


def _configured_models() -> dict[str, str]:
    """Modèles effectivement utilisés (env ou défauts `reason_route_matrix`)."""
    from team.reason_llm import reason_local_model

    return {
        "dialogue_local": os.environ.get("LBG_DIALOGUE_LLM_MODEL", "").strip(),
        "dialogue_fast": os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip(),
        "reason_default": reason_local_model(profile="default"),
        "reason_forge": reason_local_model(profile="forge"),
        "reason_router": reason_local_model(profile="router"),
        "reason_json": reason_local_model(profile="json"),
        "reason_code": reason_local_model(profile="code"),
        "reason_pm": reason_local_model(profile="pm"),
        "reason_fast": reason_local_model(profile="fast"),
        "jobs_planner": os.environ.get("LBG_JOBS_PLANNER_LLM_MODEL", "").strip(),
        "companion": os.environ.get("LBG_COMPANION_LLM_MODEL", "").strip(),
    }


def _fetch_tags(base: str, *, timeout: float = 10.0) -> dict[str, Any]:
    with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
        r = client.get(f"{base}/api/tags")
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise RuntimeError("réponse /api/tags invalide")
        models_raw = data.get("models") or []
        installed: list[dict[str, Any]] = []
        names: set[str] = set()
        for m in models_raw:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name") or "")
            if name:
                names.add(name)
                details = m.get("details") if isinstance(m.get("details"), dict) else {}
                installed.append(
                    {
                        "name": name,
                        "size_gb": round(int(m.get("size") or 0) / 1e9, 2),
                        "params": details.get("parameter_size"),
                        "quant": details.get("quantization_level"),
                        "family": details.get("family"),
                    }
                )
        return {"installed": installed, "names": names}


def _model_available(name: str, installed: set[str]) -> bool:
    if not name:
        return True
    if name in installed:
        return True
    base = name.split(":")[0]
    return any(n.startswith(base + ":") or n == base for n in installed)


def _recommendations(
    *,
    heavy_installed: list[dict[str, Any]],
    light_installed: list[dict[str, Any]],
    config: dict[str, str],
    gaps: list[str],
    light_url: str,
) -> list[str]:
    heavy_names = {m["name"] for m in heavy_installed}
    light_names = {m["name"] for m in light_installed}
    recs: list[str] = []

    has_e2b = any("e2b" in n for n in heavy_names)
    has_26b = any("26b" in n for n in heavy_names)
    has_light = len(light_names) > 0

    if gaps:
        recs.append("Corriger modèles manquants : heavy `.110` ou light `.111` (`ollama pull`).")

    if has_light:
        recs.append(
            f"Routage/JSON sur light {light_url} — modèles : {', '.join(sorted(light_names)[:6])}."
        )
    else:
        recs.append(
            "Light 111 vide/injoignable — LBG_REASON_LIGHT_BASE_URL + pull "
            "qwen2.5:3b (Clean) et llama3.2:3b (Fast) sur le NUC. "
            "Ne pas réintroduire gemma3:4b (écarté). Voir docs/local_llm_route_matrix.md."
        )

    if has_e2b:
        recs.append("Forge/Iris : LBG_REASON_MODEL_FORGE=gemma4:e2b (heavy 110 CT).")
        recs.append("Failover light→heavy : LBG_REASON_LIGHT_FAILOVER_HEAVY=1 + gemma4:e2b.")
    if has_26b:
        recs.append("Code/PM : gemma4:26b sur heavy 110 (latence CPU acceptable hors dialogue).")

    if not os.environ.get("LBG_REASON_LIGHT_BASE_URL", "").strip():
        recs.append("Poser LBG_REASON_LIGHT_BASE_URL=http://192.168.0.111:11434 sur 140.")

    recs.append("Heavy 110 = CT Ollama-only ; front Pilot legacy = .112:8080 (hors charge LLM).")
    recs.append("CT heavy : OLLAMA_MAX_LOADED_MODELS=1 pour éviter swap sur 20 Go.")

    return recs


def _audit_one_host(base: str, *, tier: str) -> dict[str, Any]:
    try:
        tags = _fetch_tags(base)
        return {
            "ok": True,
            "tier": tier,
            "base_url": base,
            "model_count": len(tags["installed"]),
            "installed": tags["installed"],
            "names": sorted(tags["names"]),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "tier": tier,
            "base_url": base,
            "model_count": 0,
            "installed": [],
            "names": [],
            "error": str(exc),
        }


def audit_ollama_lan(*, base_url: str | None = None) -> dict[str, Any]:
    """Audit dual : modèles heavy (110) + light (111) vs rôles LBG."""
    heavy_url = (base_url or ollama_base_url()).rstrip("/")
    light_url = light_ollama_base_url()
    config = _configured_models()
    gaps: list[str] = []
    missing: list[dict[str, str]] = []

    heavy = _audit_one_host(heavy_url, tier="heavy")
    light = _audit_one_host(light_url, tier="light")

    heavy_names: set[str] = set(heavy.get("names") or [])
    light_names: set[str] = set(light.get("names") or [])

    if heavy.get("error"):
        gaps.append(f"heavy injoignable ({heavy_url}): {heavy['error']}")
    if light.get("error"):
        gaps.append(f"light injoignable ({light_url}): {light['error']}")

    for role, model in config.items():
        if not model:
            continue
        role_url = _base_url_for_role(role)
        if not _is_local_ollama_base(role_url):
            continue
        if role in _LIGHT_ROLES or role_url.rstrip("/") == light_url.rstrip("/"):
            pool, label = light_names, "111-light"
        else:
            pool, label = heavy_names, "110-heavy"
        if not _model_available(model, pool):
            gaps.append(f"{role}: {model} absent sur {label}")
            missing.append({"role": role, "model": model, "base_url": role_url, "host": label})

    failover = os.environ.get("LBG_REASON_LIGHT_FAILOVER_HEAVY", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    ok = bool(heavy.get("ok")) and len(heavy_names) > 0
    heavy_blocking = [g for g in gaps if "110-heavy" in g or g.startswith("heavy injoignable")]
    if heavy_blocking:
        ok = False
    # Light KO ou modèle light manquant : OK soft si failover vers heavy.
    if any("111-light" in g or g.startswith("light injoignable") for g in gaps):
        if failover and heavy.get("ok") and len(heavy_names) > 0 and not heavy_blocking:
            ok = True
        else:
            ok = False

    recs = _recommendations(
        heavy_installed=list(heavy.get("installed") or []),
        light_installed=list(light.get("installed") or []),
        config=config,
        gaps=gaps,
        light_url=light_url,
    )

    return {
        "ok": ok,
        "track": "ollama_audit_dual_110_111",
        "base_url": heavy_url,
        "light_base_url": light_url,
        "model_count": int(heavy.get("model_count") or 0) + int(light.get("model_count") or 0),
        "installed": list(heavy.get("installed") or []),
        "heavy": {k: v for k, v in heavy.items() if k != "installed"} | {"installed": heavy.get("installed")},
        "light": {k: v for k, v in light.items() if k != "installed"} | {"installed": light.get("installed")},
        "configured": config,
        "gaps": gaps,
        "missing_models": missing,
        "recommendations": recs,
        "host_role": "dual_llm_110_heavy_111_light",
        "gpu": False,
        "topology": {
            "heavy": heavy_url,
            "light": light_url,
            "front_legacy": "http://192.168.0.112:8080",
        },
    }
