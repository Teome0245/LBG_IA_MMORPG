"""Backend REASON — chaîne local 110 (H24) + fallback cloud (Groq/Claude)."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx


def reason_llm_enabled() -> bool:
    if os.environ.get("LBG_REASON_LLM_DISABLED", "0").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return bool(reason_routes())


def reason_failover_enabled() -> bool:
    return os.environ.get("LBG_REASON_FAILOVER", "1").strip().lower() in ("1", "true", "yes", "on")


def reason_local_base_url() -> str:
    return (
        os.environ.get("LBG_REASON_LOCAL_BASE_URL", "").strip()
        or os.environ.get("LBG_REASON_BASE_URL", "").strip()
        or os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.110:11434").strip()
    ).rstrip("/")


def reason_local_model(*, profile: str = "default") -> str:
    """Profils CPU 110 : e2b (forge/rapide) vs 26b (synthèse qualité)."""
    p = (profile or "default").strip().lower()
    by_profile = {
        "forge": os.environ.get("LBG_REASON_MODEL_FORGE", "").strip(),
        "pm": os.environ.get("LBG_REASON_MODEL_PM", "").strip(),
        "fast": os.environ.get("LBG_REASON_MODEL_FAST", "").strip(),
        "dialogue": os.environ.get("LBG_REASON_MODEL_DIALOGUE", "").strip(),
    }
    if by_profile.get(p):
        return by_profile[p]
    if p in ("forge", "fast", "iris"):
        return os.environ.get("LBG_REASON_MODEL_FORGE", "").strip() or "gemma4:e2b"
    if p in ("pm", "dialogue", "synthesis"):
        return os.environ.get("LBG_REASON_MODEL_PM", "").strip() or "gemma4:26b"
    return (
        os.environ.get("LBG_REASON_LOCAL_MODEL", "").strip()
        or os.environ.get("LBG_REASON_MODEL", "").strip()
        or os.environ.get("LBG_DIALOGUE_LLM_MODEL", "").strip()
        or "gemma4:e2b"
    )


def reason_local_model_legacy() -> str:
    return reason_local_model(profile="default")


def reason_cloud_base_url() -> str:
    return (
        os.environ.get("LBG_REASON_CLOUD_BASE_URL", "").strip()
        or os.environ.get("LBG_DIALOGUE_FAST_BASE_URL", "").strip()
    ).rstrip("/")


def reason_cloud_model() -> str:
    return (
        os.environ.get("LBG_REASON_CLOUD_MODEL", "").strip()
        or os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip()
        or "llama-3.3-70b-versatile"
    )


def reason_cloud_api_key() -> str:
    return (
        os.environ.get("LBG_REASON_CLOUD_API_KEY", "").strip()
        or os.environ.get("LBG_REASON_API_KEY", "").strip()
        or os.environ.get("LBG_DIALOGUE_FAST_API_KEY", "").strip()
    )


# Compat anciennes vars
def reason_base_url() -> str:
    return reason_local_base_url() or reason_cloud_base_url()


def reason_model() -> str:
    return reason_local_model(profile="default")


def reason_api_key() -> str:
    return reason_cloud_api_key()


def reason_routes(*, prefer_cloud: bool = False, profile: str = "default") -> list[dict[str, str]]:
    """Ordre : local 110 d'abord (H24), puis cloud si failover ou échec local."""
    routes: list[dict[str, str]] = []
    local_url = reason_local_base_url()
    if local_url and not prefer_cloud:
        routes.append(
            {
                "tier": "local",
                "base_url": local_url,
                "model": reason_local_model(profile=profile),
                "api_key": "",
                "profile": profile,
            }
        )
    cloud_url = reason_cloud_base_url()
    cloud_key = reason_cloud_api_key()
    if cloud_url and cloud_key:
        routes.append(
            {
                "tier": "cloud",
                "base_url": cloud_url,
                "model": reason_cloud_model(),
                "api_key": cloud_key,
            }
        )
    if prefer_cloud and cloud_url and cloud_key:
        return [r for r in routes if r["tier"] == "cloud"] + [r for r in routes if r["tier"] == "local"]
    return routes


def _chat_completions_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/chat/completions"
    if "api.anthropic.com" in b:
        return f"{b}/v1/messages"
    return f"{b}/v1/chat/completions"


def _extract_text(data: Any) -> str:
    if not isinstance(data, dict):
        raise RuntimeError("Réponse LLM invalide")
    if "content" in data and isinstance(data["content"], list):
        parts: list[str] = []
        for block in data["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        text = "".join(parts).strip()
        if text:
            return text
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        ch = choices[0]
        if isinstance(ch, dict):
            msg = ch.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            text = ch.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    raise RuntimeError("Réponse LLM vide")


def _call_route(
    route: dict[str, str],
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any]:
    base = route["base_url"]
    model = route["model"]
    key = route.get("api_key") or ""
    url = _chat_completions_url(base)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    if "api.anthropic.com" in base:
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
        }
    else:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        text = _extract_text(resp.json())
        return {"ok": True, "text": text, "model": model, "base_url": base, "tier": route["tier"]}


def complete_reason(
    *,
    system: str,
    user: str,
    temperature: float | None = None,
    prefer_cloud: bool | None = None,
    profile: str = "forge",
) -> dict[str, Any]:
    """Appel REASON avec failover : Ollama 110 (profil) → cloud si échec."""
    if not reason_llm_enabled():
        return {"ok": False, "error": "LBG_REASON_LLM_DISABLED ou aucune route", "skipped": True}

    prefer = prefer_cloud
    if prefer is None:
        prefer = os.environ.get("LBG_REASON_PREFER_CLOUD", "0").strip().lower() in ("1", "true", "yes", "on")

    temp = temperature if temperature is not None else float(os.environ.get("LBG_REASON_TEMPERATURE", "0.2"))
    max_tokens = int(os.environ.get("LBG_REASON_MAX_TOKENS", "2048"))
    timeout = float(os.environ.get("LBG_REASON_TIMEOUT_S", "90"))

    routes = reason_routes(prefer_cloud=prefer, profile=profile)
    errors: list[str] = []

    for i, route in enumerate(routes):
        try:
            out = _call_route(route, system=system, user=user, temperature=temp, max_tokens=max_tokens, timeout=timeout)
            out["route_index"] = i
            return out
        except Exception as exc:
            errors.append(f"{route['tier']}:{exc}")
            if not reason_failover_enabled() or i == len(routes) - 1:
                break

    return {
        "ok": False,
        "error": "; ".join(errors) or "aucune route REASON",
        "routes_tried": len(routes),
    }


def probe_reason_local() -> dict[str, Any]:
    """Sonde Ollama 110 — la VM 110 doit rester up H24 (distinct du poste 10)."""
    url = reason_local_base_url().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    tags = f"{url}/api/tags"
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
            r = client.get(tags)
            ok = r.status_code == 200
            return {"ok": ok, "url": tags, "tier": "local", "host": "110"}
    except Exception as exc:
        return {"ok": False, "url": tags, "error": str(exc), "tier": "local"}


def extract_code_block(text: str, *, lang: str = "gdscript") -> str | None:
    pattern = rf"```{re.escape(lang)}\s*(.*?)```"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    stripped = text.strip()
    return stripped if stripped.startswith("extends ") or stripped.startswith("#") else None
