"""
Pont minimal orchestrateur → « agents » : exécution déterministe par `routed_to`.

Dialogue : si `LBG_AGENT_DIALOGUE_URL` est défini, appel HTTP `POST {url}/invoke`.

`LBG_AGENT_DIALOGUE_TIMEOUT` — secondes pour la **réponse** (défaut 120) : l’agent peut
appeler un LLM (Ollama) ; 5 s est trop court.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import httpx

from lbg_agents.combat_stub import run_combat_stub
from lbg_agents.lyra_bridge import step_context_lyra_once
from lbg_agents.devops_executor import (
    default_action_from_text,
    execution_requires_approval,
    is_devops_dry_run,
    run_devops_action,
)
from lbg_agents.pm_stub import run_pm_stub
from lbg_agents.quests_stub import run_quests_stub
from lbg_agents.world_stub import run_world_stub
from lbg_agents.desktop_executor import run_desktop_action
from lbg_agents.opengame_executor import run_opengame_action


def _dialogue_http_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_AGENT_DIALOGUE_TIMEOUT", "120").strip()
    try:
        read_s = max(5.0, float(raw))
    except ValueError:
        read_s = 120.0
    return httpx.Timeout(connect=15.0, read=read_s, write=30.0, pool=10.0)


def _quests_http_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_AGENT_QUESTS_TIMEOUT", "30").strip()
    try:
        read_s = max(2.0, float(raw))
    except ValueError:
        read_s = 30.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def _combat_http_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_AGENT_COMBAT_TIMEOUT", "30").strip()
    try:
        read_s = max(2.0, float(raw))
    except ValueError:
        read_s = 30.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def _pm_http_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_AGENT_PM_TIMEOUT", "45").strip()
    try:
        read_s = max(2.0, float(raw))
    except ValueError:
        read_s = 45.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def invoke_after_route(
    routed_to: str,
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    t0 = time.perf_counter()
    trace_id = context.get("_trace_id") if isinstance(context, dict) else None
    trace_id = trace_id if isinstance(trace_id, str) and trace_id.strip() else None
    handler = _HANDLERS.get(routed_to, _fallback)
    out = handler(actor_id=actor_id, text=text, context=context)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    try:
        agent = out.get("agent") if isinstance(out, dict) else None
        handler_kind = out.get("handler") if isinstance(out, dict) else None
    except Exception:
        agent = None
        handler_kind = None
    print(
        json.dumps(
            {
                "event": "agents.dispatch",
                "trace_id": trace_id,
                "actor_id": actor_id,
                "routed_to": routed_to,
                "agent": agent,
                "handler": handler_kind,
                "elapsed_ms": elapsed_ms,
            },
            ensure_ascii=False,
        )
    )
    return out


def _echo(kind: str, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    snippet = text if len(text) <= 120 else text[:117] + "..."
    out: dict[str, Any] = {
        "agent": "minimal_stub",
        "handler": kind,
        "actor_id": actor_id,
        "text_snippet": snippet,
        "context_keys": sorted(context.keys()),
    }
    # Contrat Lyra (voir docs/lyra.md) : echo + pas de jauges si `lyra_engine` dispo (mmo_server).
    _, lyra_out = step_context_lyra_once(context if isinstance(context, dict) else {})
    if lyra_out is not None:
        out["lyra"] = lyra_out
    return out


def _dialogue(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip().rstrip("/")
    if not base:
        return _echo("dialogue", actor_id, text, context)
    ctx_use, lyra_out = step_context_lyra_once(context if isinstance(context, dict) else {})
    try:
        with httpx.Client(timeout=_dialogue_http_timeout()) as client:
            r = client.post(
                f"{base}/invoke",
                json={"actor_id": actor_id, "text": text, "context": ctx_use},
            )
        if r.status_code >= 400:
            return {
                "agent": "http_dialogue",
                "error": f"HTTP {r.status_code}",
                "body_preview": r.text[:200],
                **_echo("dialogue_stub_fallback", actor_id, text, context),
            }
        data = r.json()
        if not isinstance(data, dict):
            data = {"payload": data}
        out: dict[str, Any] = {"agent": "http_dialogue", "remote": data}
        if isinstance(data.get("commit"), dict):
            out["commit"] = data["commit"]
        meta = data.get("meta")
        if isinstance(meta, dict):
            dpr = meta.get("dialogue_profile_resolved")
            if isinstance(dpr, str) and dpr.strip():
                out["dialogue_profile_resolved"] = dpr.strip()
        if lyra_out is not None:
            out["lyra"] = lyra_out
        return out
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        if isinstance(e, httpx.ReadTimeout):
            err_msg = (
                f"{detail} — réponse dialogue trop lente (souvent LLM/Ollama). "
                "Augmenter LBG_AGENT_DIALOGUE_TIMEOUT (secondes, défaut 120) pour l’orchestrator."
            )
        elif isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
            err_msg = (
                f"{detail} | rien n’écoute sur {base}/invoke — "
                "démarrer l’agent dialogue (port 8020) : "
                "`uvicorn lbg_agents.dialogue_http_app:app --host 0.0.0.0 --port 8020` "
                "ou `systemctl start lbg-agent-dialogue`."
            )
        else:
            err_msg = (
                f"{detail} | appel {base}/invoke échoué — vérifier l’agent dialogue et le réseau."
            )
        return {
            "agent": "http_dialogue",
            "error": err_msg,
            **_echo("dialogue_stub_fallback", actor_id, text, context),
        }


def _quests(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("LBG_AGENT_QUESTS_URL", "").strip().rstrip("/")
    if base:
        try:
            with httpx.Client(timeout=_quests_http_timeout()) as client:
                r = client.post(
                    f"{base}/invoke",
                    json={"actor_id": actor_id, "text": text, "context": context},
                )
            if r.status_code >= 400:
                return {
                    "agent": "http_quests",
                    "error": f"HTTP {r.status_code}",
                    "body_preview": r.text[:200],
                    **_echo("quests_stub_fallback", actor_id, text, context),
                }
            data = r.json()
            if not isinstance(data, dict):
                return {"agent": "http_quests", "remote": data}
            merged = dict(data)
            merged["agent"] = "http_quests"
            return merged
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            return {
                "agent": "http_quests",
                "error": f"{detail} | appel {base}/invoke échoué — vérifier l’agent quests et le réseau.",
                **_echo("quests_stub_fallback", actor_id, text, context),
            }

    return run_quests_stub(actor_id=actor_id, text=text, context=context)


def _combat(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("LBG_AGENT_COMBAT_URL", "").strip().rstrip("/")
    if base:
        try:
            with httpx.Client(timeout=_combat_http_timeout()) as client:
                r = client.post(
                    f"{base}/invoke",
                    json={"actor_id": actor_id, "text": text, "context": context},
                )
            if r.status_code >= 400:
                return {
                    "agent": "http_combat",
                    "error": f"HTTP {r.status_code}",
                    "body_preview": r.text[:200],
                    **_echo("combat_stub_fallback", actor_id, text, context),
                }
            data = r.json()
            if not isinstance(data, dict):
                return {"agent": "http_combat", "remote": data}
            merged = dict(data)
            merged["agent"] = "http_combat"
            return merged
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            return {
                "agent": "http_combat",
                "error": f"{detail} | appel {base}/invoke échoué — vérifier l’agent combat et le réseau.",
                **_echo("combat_stub_fallback", actor_id, text, context),
            }

    return run_combat_stub(actor_id=actor_id, text=text, context=context)


def _pm(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("LBG_AGENT_PM_URL", "").strip().rstrip("/")
    if base:
        try:
            with httpx.Client(timeout=_pm_http_timeout()) as client:
                r = client.post(
                    f"{base}/invoke",
                    json={"actor_id": actor_id, "text": text, "context": context},
                )
            if r.status_code >= 400:
                fb = run_pm_stub(actor_id=actor_id, text=text, context=context)
                return {
                    **fb,
                    "agent": "http_pm",
                    "error": f"HTTP {r.status_code}",
                    "body_preview": r.text[:200],
                }
            data = r.json()
            if not isinstance(data, dict):
                return {"agent": "http_pm", "remote": data}
            merged = dict(data)
            merged["agent"] = merged.get("agent") or "http_pm"
            return merged
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            fb = run_pm_stub(actor_id=actor_id, text=text, context=context)
            return {
                **fb,
                "agent": "http_pm",
                "error": f"{detail} | appel {base}/invoke échoué — vérifier l’agent PM et le réseau.",
            }
    return run_pm_stub(actor_id=actor_id, text=text, context=context)


def _devops(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    raw = context.get("devops_action")
    if context.get("devops_selfcheck") is True:
        if not isinstance(raw, dict):
            raw = {"kind": "selfcheck"}
        elif not raw.get("kind"):
            raw = {**raw, "kind": "selfcheck"}
    if not isinstance(raw, dict):
        inferred = default_action_from_text(text)
        if inferred is not None:
            raw = inferred
        else:
            dr = is_devops_dry_run(context)
            return {
                "agent": "devops_executor",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "error": "Aucune devops_action dans context et texte non reconnu pour sonde par défaut.",
                "hint": 'Ex. {"kind":"http_get","url":"http://127.0.0.1:8010/healthz"}',
                "meta": {"dry_run": dr, "execution_gated": execution_requires_approval()},
            }
    return run_devops_action(actor_id=actor_id, text=text, action=raw, context=context)


def _desktop(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Hybrid desktop control.

    Par design, on exige `context.desktop_action` structuré, sinon on refuse :
    éviter qu’un texte ambigu déclenche une action PC.
    """
    base = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip().rstrip("/")
    raw = context.get("desktop_action")
    if not isinstance(raw, dict):
        return {
            "agent": "desktop_dispatch",
            "handler": "desktop",
            "actor_id": actor_id,
            "request_text": text,
            "ok": False,
            "outcome": "bad_request",
            "error": "Aucune desktop_action dans context.",
            "hint": 'Ex. {"desktop_action": {"kind":"open_url","url":"https://example.org"}} ; search_web_open / mail_imap_preview si variables d’activation correspondantes',
        }

    # Mode hybride : exécution attendue sur un worker Windows.
    if base:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(f"{base}/invoke", json={"actor_id": actor_id, "text": text, "context": context})
            if r.status_code >= 400:
                return {
                    "agent": "http_desktop",
                    "error": f"HTTP {r.status_code}",
                    "body_preview": r.text[:200],
                }
            data = r.json()
            if not isinstance(data, dict):
                return {"agent": "http_desktop", "remote": data}
            merged = dict(data)
            merged["agent"] = merged.get("agent") or "http_desktop"
            return merged
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            return {
                "agent": "http_desktop",
                "error": (
                    f"{detail} | appel {base}/invoke échoué — vérifier l’agent desktop Windows et le réseau."
                ),
            }

    # Fallback dev (si on veut lancer le worker sur Linux pour tests) : exécution locale.
    return run_desktop_action(actor_id=actor_id, text=text, action=raw, context=context)


def _opengame(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Forge OpenGame : action structurée obligatoire.

    Cela évite qu'une phrase ambiguë déclenche une génération de code.
    """
    raw = context.get("opengame_action")
    if not isinstance(raw, dict):
        return {
            "agent": "opengame_dispatch",
            "handler": "opengame",
            "actor_id": actor_id,
            "request_text": text,
            "ok": False,
            "outcome": "bad_request",
            "error": "Aucune opengame_action dans context.",
            "hint": 'Ex. {"opengame_action":{"kind":"generate_prototype","project_name":"snake","prompt":"Build a Snake clone"}}',
        }
    return run_opengame_action(actor_id=actor_id, text=text, action=raw, context=context)


def _fallback(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    return _echo("fallback", actor_id, text, context)


def _world(actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    return run_world_stub(actor_id=actor_id, text=text, context=context)


_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "agent.dialogue": _dialogue,
    "agent.quests": _quests,
    "agent.combat": _combat,
    "agent.pm": _pm,
    "agent.devops": _devops,
    "agent.desktop": _desktop,
    "agent.opengame": _opengame,
    "agent.world": _world,
    "agent.fallback": _fallback,
}
