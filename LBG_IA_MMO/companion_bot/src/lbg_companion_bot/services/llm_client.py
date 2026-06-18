from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncio
import httpx


@dataclass(frozen=True)
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _choice_assistant_text(choice: dict[str, Any]) -> str:
    msg = choice.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        # variantes (serveurs exposant du reasoning séparément)
        for k in ("reasoning_content", "reasoning", "thinking"):
            alt = msg.get(k)
            if isinstance(alt, str) and alt.strip():
                return alt.strip()
    legacy = choice.get("text")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()
    return ""


def _parse_openai_chat_completions(data: Any) -> tuple[str, LlmUsage]:
    if not isinstance(data, dict):
        raise RuntimeError("Réponse LLM invalide: type")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Réponse LLM invalide: pas de choices")
    usage_obj = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    try:
        pt = int(usage_obj.get("prompt_tokens", 0))
    except Exception:
        pt = 0
    try:
        ct = int(usage_obj.get("completion_tokens", 0))
    except Exception:
        ct = 0
    usage = LlmUsage(prompt_tokens=max(0, pt), completion_tokens=max(0, ct))
    for ch in choices:
        if not isinstance(ch, dict):
            continue
        extracted = _choice_assistant_text(ch)
        if extracted.strip():
            return extracted.strip(), usage
    raise RuntimeError("Réponse LLM vide")


def _ollama_base_from_openai_base(base_url: str) -> str | None:
    """
    Beaucoup d'installations Ollama exposent un endpoint OpenAI-compatible (/v1),
    mais il peut être instable / lent selon versions et modèles. En fallback,
    on peut appeler l'API native (/api/chat) sur la même origine.
    """
    b = (base_url or "").rstrip("/")
    if not b:
        return None
    if b.endswith("/v1"):
        return b[: -len("/v1")]
    return b


def _parse_ollama_chat(data: Any) -> str:
    # Réponse non-stream: {"message":{"role":"assistant","content":"..."}, ...}
    if not isinstance(data, dict):
        raise RuntimeError("Réponse Ollama invalide: type")
    msg = data.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    # Certaines versions renvoient directement "response"
    resp = data.get("response")
    if isinstance(resp, str) and resp.strip():
        return resp.strip()
    raise RuntimeError("Réponse Ollama vide")


class OpenAiCompatClient:
    def __init__(self, *, base_url: str, api_key: str = "", timeout_s: float = 60.0) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key.strip()
        self._timeout = max(5.0, float(timeout_s))

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, LlmUsage]:
        if not self._base:
            raise RuntimeError("LLM indisponible (base_url vide)")
        url = f"{self._base}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                r = await asyncio.wait_for(client.post(url, json=payload, headers=headers), timeout=self._timeout)
            if r.status_code >= 400:
                body = (r.text or "")[:1500]
                raise RuntimeError(f"HTTP {r.status_code} (openai chat/completions): {body}")
            return _parse_openai_chat_completions(r.json())
        except Exception as e:
            # Fallback Ollama natif si on pointe vers Ollama.
            ollama_base = _ollama_base_from_openai_base(self._base)
            if not ollama_base:
                raise
            ollama_url = f"{ollama_base}/api/chat"
            ollama_payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": float(temperature)},
            }
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                    r2 = await asyncio.wait_for(
                        client.post(ollama_url, json=ollama_payload, headers={"Content-Type": "application/json"}),
                        timeout=self._timeout,
                    )
                if r2.status_code >= 400:
                    body2 = (r2.text or "")[:1500]
                    raise RuntimeError(f"HTTP {r2.status_code} (ollama /api/chat): {body2}") from e
                txt = _parse_ollama_chat(r2.json())
                return txt, LlmUsage()
            except Exception:
                # Remonte l'erreur initiale (OpenAI) pour debug, mais avec contexte.
                raise RuntimeError(f"LLM indisponible (openai endpoint) : {e}") from e

    def chat_sync(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, LlmUsage]:
        if not self._base:
            raise RuntimeError("LLM indisponible (base_url vide)")
        url = f"{self._base}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(self._timeout)) as client:
                r = client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                body = (r.text or "")[:1500]
                raise RuntimeError(f"HTTP {r.status_code} (openai chat/completions): {body}")
            return _parse_openai_chat_completions(r.json())
        except Exception as e:
            ollama_base = _ollama_base_from_openai_base(self._base)
            if not ollama_base:
                raise
            ollama_url = f"{ollama_base}/api/chat"
            ollama_payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": float(temperature)},
            }
            try:
                with httpx.Client(timeout=httpx.Timeout(self._timeout)) as client:
                    r2 = client.post(ollama_url, json=ollama_payload, headers={"Content-Type": "application/json"})
                if r2.status_code >= 400:
                    body2 = (r2.text or "")[:1500]
                    raise RuntimeError(f"HTTP {r2.status_code} (ollama /api/chat): {body2}") from e
                txt = _parse_ollama_chat(r2.json())
                return txt, LlmUsage()
            except Exception:
                raise RuntimeError(f"LLM indisponible (openai endpoint) : {e}") from e

