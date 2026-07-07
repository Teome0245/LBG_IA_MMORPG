"""
Assistant chef de projet avec LLM — s'appuie sur plan_de_route.md + historique.

Variables (repli sur LBG_DIALOGUE_LLM_* si absentes) :
- LBG_PM_LLM_DISABLED — si 1 : toujours stub
- LBG_PM_LLM_BASE_URL, LBG_PM_LLM_MODEL, LBG_PM_LLM_API_KEY, LBG_PM_LLM_TIMEOUT
- LBG_REPO_ROOT — racine repo pour grep / arbre (optionnel)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Iterator

import httpx

from lbg_agents.assistant_tools import (
    format_tools_for_llm,
    parse_tool_calls_from_llm,
    run_tool_pipeline,
    strip_tool_tags,
)
from lbg_agents.pm_stub import (
    _extract_etape_actuelle,
    _extract_file_attente,
    _extract_milestones,
    _milestones_max,
    _read_plan_text,
    run_pm_stub,
)
from lbg_agents.repo_context import repo_context_block

PM_SYSTEM_BASE = """Tu es l'assistant chef de projet **LBG** (orchestrateur IA + MMO Core3 Prime + infra LAN).
Tu parles à l'initiateur / l'opérateur du projet en **français**, ton naturel et précis (style copilote Cursor).
Tu t'appuies sur le **plan de route** et le **contexte codebase** ci-dessous — ne fabrique pas d'avancement non documenté.
Si une information manque, dis-le et propose une prochaine action concrète (smoke, doc, ticket).
Pas de raisonnement interne visible, pas de listes « Thinking Process ».

**Outils** (lecture seule, déjà exécutés pour toi quand pertinent) :
- `grep` — recherche dans le repo
- `ssh` — commandes allowlist sur linux-N (uptime, systemctl, free, df)
- `core3` — healthz sidecar MMO

Si tu as besoin d'un outil supplémentaire non couvert, demande à l'opérateur en Ops/Supervisé.
Pour demander un outil toi-même (rare), écris exactement :
<lbg_tool>{"name":"grep","args":{"pattern":"..."}}</lbg_tool>"""


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


def pm_llm_disabled() -> bool:
    if _truthy(os.environ.get("LBG_PM_LLM_DISABLED")):
        return True
    if _truthy(os.environ.get("LBG_DIALOGUE_LLM_DISABLED")):
        return True
    return False


def pm_llm_enabled() -> bool:
    return not pm_llm_disabled() and bool(_base_url())


def _env_pm_or_dialogue(key_pm: str, key_dialogue: str, default: str = "") -> str:
    v = os.environ.get(key_pm, "").strip()
    if v:
        return v
    return os.environ.get(key_dialogue, default).strip()


def _base_url() -> str:
    return _env_pm_or_dialogue("LBG_PM_LLM_BASE_URL", "LBG_DIALOGUE_LLM_BASE_URL", "http://127.0.0.1:11434/v1")


def _model() -> str:
    return _env_pm_or_dialogue("LBG_PM_LLM_MODEL", "LBG_DIALOGUE_LLM_MODEL", "phi4-mini:latest") or "phi4-mini:latest"


def _api_key() -> str:
    return _env_pm_or_dialogue("LBG_PM_LLM_API_KEY", "LBG_DIALOGUE_LLM_API_KEY")


def _timeout_s() -> float:
    raw = _env_pm_or_dialogue("LBG_PM_LLM_TIMEOUT", "LBG_DIALOGUE_LLM_TIMEOUT", "90")
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 90.0


def _normalize_history(history: object, *, max_messages: int = 20) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, str]] = []
    for m in history:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        c = content.strip()
        if not c:
            continue
        out.append({"role": role, "content": c[:4000]})
    return out[-max_messages:]


def _plan_context_block() -> str:
    plan = _read_plan_text()
    if not plan:
        return "(Plan de route non disponible sur ce serveur — définir LBG_PM_PLAN_PATH.)"
    step = _extract_etape_actuelle(plan)
    fa = _extract_file_attente(plan)
    milestones = _extract_milestones(plan)[-_milestones_max() :]
    lines = ["## Extrait plan_de_route.md", ""]
    if step:
        lines.append(f"**Étape actuelle** : {step}")
    if fa:
        lines.append(f"**File d'attente** : {fa}")
    if milestones:
        lines.append("", "**Derniers jalons (État courant)** :")
        for m in milestones[-6:]:
            lines.append(f"- {m.get('date', '?')} — {str(m.get('summary') or '')[:200]}")
    # Corps tronqué pour le prompt
    tail = plan[-12000:] if len(plan) > 12000 else plan
    lines.extend(["", "### Fin du plan (tronqué si besoin)", tail])
    return "\n".join(lines)


def _strip_reasoning(text: str) -> str:
    s = text.strip()
    s = re.sub(r"(?is)^thinking process:.*?(?=\n\n|\Z)", "", s).strip()
    return s


def _build_system_prompt(*, user_text: str, include_repo: bool) -> str:
    blocks = [PM_SYSTEM_BASE, "", _plan_context_block()]
    if include_repo:
        blocks.extend(["", repo_context_block(user_text=user_text)])
    return "\n".join(blocks)


def _call_llm(messages: list[dict[str, str]]) -> str:
    url = f"{_base_url().rstrip('/')}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 900,
    }
    with httpx.Client(timeout=_timeout_s()) as client:
        r = client.post(url, json=payload, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Réponse LLM sans choices")
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Réponse LLM vide")
    return _strip_reasoning(content)


def _call_llm_stream(messages: list[dict[str, str]]) -> Iterator[str]:
    """Yield deltas de contenu (OpenAI-compatible streaming)."""
    url = f"{_base_url().rstrip('/')}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 900,
        "stream": True,
    }
    with httpx.Client(timeout=_timeout_s()) as client:
        with client.stream("POST", url, json=payload, headers=headers) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"LLM HTTP {r.status_code}: {r.read().decode()[:300]}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") if isinstance(data, dict) else None
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                if not isinstance(delta, dict):
                    continue
                piece = delta.get("content")
                if isinstance(piece, str) and piece:
                    yield piece


def _messages_for_turn(
    *,
    text: str,
    context: dict[str, Any],
    tool_block: str,
) -> list[dict[str, str]]:
    include_repo = context.get("pm_include_repo") is not False
    system = _build_system_prompt(user_text=text, include_repo=include_repo)
    if tool_block:
        system += "\n\n" + tool_block
    history = _normalize_history(context.get("history"))
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": text.strip()[:4000]})
    return messages


def run_pm_llm_turn(*, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Tour assistant PM — LLM + brief structuré pour le pilot."""
    stub = run_pm_stub(actor_id=actor_id, text=text, context=context)
    brief = stub.get("brief") if isinstance(stub.get("brief"), dict) else {}

    tool_results: list[dict[str, Any]] = []
    for evt in run_tool_pipeline(text):
        if evt.get("kind") == "tool_result":
            tool_results.append(evt)

    tool_block = format_tools_for_llm(tool_results)
    messages = _messages_for_turn(text=text, context=context, tool_block=tool_block)

    try:
        reply = _call_llm(messages)
        extra_calls = parse_tool_calls_from_llm(reply)
        if extra_calls:
            for spec in extra_calls:
                from lbg_agents.assistant_tools import execute_tool

                tr = execute_tool(str(spec.get("name")), dict(spec.get("args") or {}))
                tool_results.append(
                    {
                        "kind": "tool_result",
                        "tool": tr.get("tool"),
                        "args": tr.get("args"),
                        "ok": tr.get("ok"),
                        "output": tr.get("output"),
                    }
                )
            messages = _messages_for_turn(
                text=text,
                context=context,
                tool_block=format_tools_for_llm(tool_results),
            )
            reply = _call_llm(messages)
        reply = strip_tool_tags(reply)
    except Exception as e:
        err = str(e)
        return {
            **stub,
            "agent": "pm_llm_fallback",
            "reply": (
                f"(LLM indisponible : {err[:200]})\n\n"
                + _brief_to_text(brief)
            ),
            "llm_error": err[:500],
        }

    return {
        **stub,
        "agent": "pm_llm",
        "handler": "project_pm",
        "actor_id": actor_id,
        "reply": reply,
        "brief": brief,
        "tools": tool_results,
    }


def run_pm_llm_turn_stream(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Tour PM avec événements SSE : tool_*, token, done."""
    stub = run_pm_stub(actor_id=actor_id, text=text, context=context)
    brief = stub.get("brief") if isinstance(stub.get("brief"), dict) else {}

    if pm_llm_disabled() or not _base_url():
        reply = _brief_to_text(brief)
        yield {"kind": "token", "delta": reply}
        yield {"kind": "done", "reply": reply, "brief": brief, "tools": [], "agent": "pm_stub"}
        return

    tool_results: list[dict[str, Any]] = []
    for evt in run_tool_pipeline(text):
        yield evt
        if evt.get("kind") == "tool_result":
            tool_results.append(evt)

    tool_block = format_tools_for_llm(tool_results)
    messages = _messages_for_turn(text=text, context=context, tool_block=tool_block)

    parts: list[str] = []
    try:
        for delta in _call_llm_stream(messages):
            parts.append(delta)
            yield {"kind": "token", "delta": delta}
        reply = strip_tool_tags("".join(parts))
        extra_calls = parse_tool_calls_from_llm(reply)
        if extra_calls:
            from lbg_agents.assistant_tools import execute_tool

            for spec in extra_calls:
                name = str(spec.get("name"))
                args = dict(spec.get("args") or {})
                yield {"kind": "tool_start", "tool": name, "args": args}
                tr = execute_tool(name, args)
                evt = {
                    "kind": "tool_result",
                    "tool": tr.get("tool"),
                    "args": tr.get("args"),
                    "ok": tr.get("ok"),
                    "output": tr.get("output"),
                }
                yield evt
                tool_results.append(evt)
            messages2 = _messages_for_turn(
                text=text,
                context=context,
                tool_block=format_tools_for_llm(tool_results),
            )
            parts2: list[str] = []
            for delta in _call_llm_stream(messages2):
                parts2.append(delta)
                yield {"kind": "token", "delta": delta}
            reply = strip_tool_tags("".join(parts2))
    except Exception as e:
        err = str(e)
        reply = (
            f"(LLM indisponible : {err[:200]})\n\n" + _brief_to_text(brief)
        )
        yield {"kind": "token", "delta": reply}
        yield {
            "kind": "done",
            "reply": reply,
            "brief": brief,
            "tools": tool_results,
            "agent": "pm_llm_fallback",
            "llm_error": err[:500],
        }
        return

    yield {
        "kind": "done",
        "reply": reply,
        "brief": brief,
        "tools": tool_results,
        "agent": "pm_llm",
    }


def _brief_to_text(brief: dict[str, Any]) -> str:
    lines = [str(brief.get("title") or "Point projet")]
    step = brief.get("current_step")
    if isinstance(step, str) and step.strip():
        lines.append(step.strip())
    for h in (brief.get("hints") or [])[:3]:
        lines.append(f"— {h}")
    return "\n".join(lines)
