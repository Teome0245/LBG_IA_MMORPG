"""Audit Ollama VM 110 — inventaire modèles vs config LBG + recommandations."""

from __future__ import annotations

import os
from typing import Any

import httpx


def ollama_base_url() -> str:
    return (
        os.environ.get("LBG_TEAM_OPS_OLLAMA_URL", "").strip()
        or os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.110:11434").strip()
    ).rstrip("/")


def _configured_models() -> dict[str, str]:
    return {
        "dialogue_local": os.environ.get("LBG_DIALOGUE_LLM_MODEL", "").strip(),
        "dialogue_fast": os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip(),
        "reason_default": os.environ.get("LBG_REASON_LOCAL_MODEL", "").strip(),
        "reason_forge": os.environ.get("LBG_REASON_MODEL_FORGE", "").strip(),
        "reason_pm": os.environ.get("LBG_REASON_MODEL_PM", "").strip(),
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
    installed: list[dict[str, Any]],
    config: dict[str, str],
    gaps: list[str],
) -> list[str]:
    names = {m["name"] for m in installed}
    recs: list[str] = []

    has_e2b = any("e2b" in n for n in names)
    has_26b = any("26b" in n for n in names)

    if gaps:
        recs.append("Corriger les modèles manquants dans lbg.env ou `ollama pull` sur 110.")

    if has_e2b:
        recs.append("Forge/Iris/REASON rapide : LBG_REASON_MODEL_FORGE=gemma4:e2b (CPU 110, ~7 Go).")
        recs.append("Jobs planner / autoconsult léger : gemma4:e2b (déjà aligné si LBG_JOBS_PLANNER_LLM_MODEL=gemma4:e2b).")
    if has_26b:
        recs.append("Dialogue PNJ / brief Thémis : gemma4:26b (qualité, latence plus haute sur CPU).")

    if not has_e2b and has_26b:
        recs.append("Éviter gemma4:26b pour forge en boucle — latence CPU élevée.")

    fast = config.get("dialogue_fast") or ""
    if fast and "groq" not in (os.environ.get("LBG_DIALOGUE_FAST_BASE_URL") or ""):
        if not _model_available(fast, names):
            recs.append(f"Palier fast dialogue : passer à gemma4:e2b ou activer Groq cloud.")

    if not os.environ.get("LBG_REASON_LOCAL_MODEL", "").strip():
        recs.append("Définir LBG_REASON_LOCAL_* dans lbg.env (actuellement défaut code peut être obsolète).")

    recs.append("VM 110 sans GPU : limiter OLLAMA_MAX_LOADED_MODELS=1 pour éviter swap.")
    recs.append("Sonar équipe : timer lbg-team-ops-ollama-job + audit intégré ops_kind=ollama_audit.")

    return recs


def audit_ollama_lan(*, base_url: str | None = None) -> dict[str, Any]:
    """Audit complet Ollama 110 — modèles installés vs variables LBG."""
    base = (base_url or ollama_base_url()).rstrip("/")
    config = _configured_models()
    gaps: list[str] = []
    missing: list[dict[str, str]] = []

    try:
        tags = _fetch_tags(base)
        installed = tags["installed"]
        names: set[str] = tags["names"]

        for role, model in config.items():
            if not model:
                continue
            if not _model_available(model, names):
                gaps.append(f"{role}: {model} absent sur 110")
                missing.append({"role": role, "model": model})

        ok = len(gaps) == 0 and len(installed) > 0
        recs = _recommendations(installed=installed, config=config, gaps=gaps)

        return {
            "ok": ok,
            "track": "ollama_audit_110",
            "base_url": base,
            "model_count": len(installed),
            "installed": installed,
            "configured": config,
            "gaps": gaps,
            "missing_models": missing,
            "recommendations": recs,
            "host_role": "front_110_h24",
            "gpu": False,
        }
    except Exception as exc:
        return {
            "ok": False,
            "track": "ollama_audit_110",
            "base_url": base,
            "error": str(exc),
            "gaps": [f"Ollama injoignable: {exc}"],
            "recommendations": [
                "Vérifier systemctl status ollama sur 110",
                "Vérifier firewall LAN :11434 depuis 140",
            ],
        }
