from __future__ import annotations

import json
import sqlite3
from typing import Any

from hybrid_proactive_agent import AgentInternalState, HybridProactiveEngine, integration_hints

from lbg_companion_bot.services import db as svc_db
from lbg_companion_bot.services.llm_client import LlmUsage, OpenAiCompatClient
from lbg_companion_bot.settings import Settings


BASE_GUARDRAILS = (
    "Tu es un compagnon IA pour le projet LBG_IA_MMO.\n"
    "Tu t'exprimes uniquement en français.\n"
    "Tu écris uniquement le texte utile, sans exposer de JSON, sans 'thinking process'."
)


def _engine_from_state(state_obj: dict[str, Any] | None) -> HybridProactiveEngine:
    eng = HybridProactiveEngine()
    if not state_obj:
        return eng
    try:
        eng.state = AgentInternalState.model_validate(state_obj)
    except Exception:
        return HybridProactiveEngine()
    return eng


def _system_prompt(*, settings: Settings, hints: dict[str, Any], action_msg: str | None, memory_hint: str | None) -> str:
    lines = [BASE_GUARDRAILS]
    lines.append("Tu peux être proactif, poser des questions, proposer un plan simple.")
    if action_msg:
        lines.append(f"Suggestion interne (ne pas exposer comme JSON) : {action_msg}")
    if memory_hint:
        lines.append("Mémoire utile (résumés) :")
        lines.append(memory_hint)
    if hints:
        lines.append("Indices internes (ne pas exposer) :")
        lines.append(json.dumps(hints, ensure_ascii=False))
    return "\n".join(lines)


def chat_turn(
    *,
    con: sqlite3.Connection,
    settings: Settings,
    session_id: str,
    user_text: str,
    debug: bool,
) -> tuple[str, dict[str, Any] | None]:
    svc_db.ensure_session(con, session_id)

    # Charger l'état moteur
    state_obj = svc_db.load_engine_state(con, session_id=session_id)
    eng = _engine_from_state(state_obj)

    # Observer le tour utilisateur
    eng.observe_user_turn(user_text, context={"intent": "companion_chat"})
    proactive = eng.decide({"missing_info": False})
    hints = integration_hints(eng.state, None)

    # Historique pour le LLM
    history = svc_db.get_history(con, session_id=session_id, limit=settings.max_history_messages)
    messages: list[dict[str, str]] = [{"role": "system", "content": _system_prompt(settings=settings, hints=hints, action_msg=proactive.message, memory_hint=None)}]
    for m in history:
        if m.role not in ("user", "assistant"):
            continue
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_text.strip()})

    usage = LlmUsage()
    if settings.llm_disabled or not settings.llm_base_url or not settings.llm_model:
        reply = (
            "Je suis en mode minimal (LLM non configuré).\n"
            "Donne-moi `LBG_COMPANION_LLM_BASE_URL` et `LBG_COMPANION_LLM_MODEL` pour activer le chat naturel.\n"
            f"En attendant, je te propose : {proactive.message}"
        )
    else:
        client = OpenAiCompatClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout_s=settings.llm_timeout_s)
        try:
            reply, usage = client.chat_sync(
                model=settings.llm_model,
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        except Exception:
            # Ne jamais bloquer l'UI : si le LLM est indisponible/timeout, on répond en mode minimal.
            usage = LlmUsage()
            reply = proactive.message.strip() or "Je suis là. Dis-moi ton objectif principal en 1 phrase."

    # Persister messages + état moteur
    svc_db.add_message(con, session_id=session_id, role="user", content=user_text.strip())
    svc_db.add_message(con, session_id=session_id, role="assistant", content=reply.strip())
    svc_db.save_engine_state(con, session_id=session_id, state=eng.state.model_dump())

    if debug:
        dbg: dict[str, Any] = {
            "mode": eng.state.mode,
            "tension": eng.state.tension,
            "curiosite": eng.state.curiosite,
            "proactive_action": proactive.model_dump(),
            "hints": hints,
            "llm_usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens},
        }
        return reply, dbg
    return reply, None


def _quota_allows_nudge(*, settings: Settings, meta: svc_db.SessionMeta, now: float) -> tuple[bool, svc_db.SessionMeta, str | None]:
    if not settings.autonomous_tick_enabled:
        return (False, meta, "autonomous tick disabled")
    # Reset fenêtre si expirée
    window_start = meta.window_start_ts
    window_nudges = meta.window_nudges
    if (now - window_start) >= settings.autonomous_window_s:
        window_start = now
        window_nudges = 0
    if settings.autonomous_max_nudges_per_window > 0 and window_nudges >= settings.autonomous_max_nudges_per_window:
        return (False, svc_db.SessionMeta(meta.last_tick_ts, window_start, window_nudges, meta.last_nudge_ts), "window quota reached")
    if meta.last_nudge_ts and (now - meta.last_nudge_ts) < settings.autonomous_min_nudge_interval_s:
        return (False, svc_db.SessionMeta(meta.last_tick_ts, window_start, window_nudges, meta.last_nudge_ts), "min nudge interval")
    return (True, svc_db.SessionMeta(meta.last_tick_ts, window_start, window_nudges, meta.last_nudge_ts), None)


def autonomous_tick(
    *,
    con: sqlite3.Connection,
    settings: Settings,
    session_id: str,
    debug: bool,
) -> tuple[str | None, dict[str, Any] | None]:
    """
    Avance la vie autonome d'une session (tick_silence).
    Retourne un nudge texte (ou None si rien à dire) + debug opt-in.
    """
    svc_db.ensure_session(con, session_id)
    now = svc_db.now_ts()

    # Charger état + meta
    state_obj = svc_db.load_engine_state(con, session_id=session_id)
    eng = _engine_from_state(state_obj)
    meta = svc_db.get_session_meta(con, session_id=session_id)

    dt = max(0.0, float(now - meta.last_tick_ts))
    eng.tick_silence(dt)

    # Par défaut : seulement si le moteur est en mode autonome
    action = eng.decide({})
    hints = integration_hints(eng.state, None)

    allowed, meta2, deny_reason = _quota_allows_nudge(settings=settings, meta=meta, now=now)
    nudge: str | None = None
    if allowed and action.mode == "autonome" and action.message.strip():
        nudge = action.message.strip()
        meta2 = svc_db.SessionMeta(
            last_tick_ts=now,
            window_start_ts=meta2.window_start_ts,
            window_nudges=meta2.window_nudges + 1,
            last_nudge_ts=now,
        )
        # Persister le nudge dans l'historique comme message assistant (visibilité UI future)
        svc_db.add_message(con, session_id=session_id, role="assistant", content=nudge)
        eng.cooldown_decay()
    else:
        meta2 = svc_db.SessionMeta(
            last_tick_ts=now,
            window_start_ts=meta2.window_start_ts,
            window_nudges=meta2.window_nudges,
            last_nudge_ts=meta2.last_nudge_ts,
        )

    svc_db.save_engine_state(con, session_id=session_id, state=eng.state.model_dump())
    svc_db.save_session_meta(con, session_id=session_id, meta=meta2)

    if debug:
        dbg: dict[str, Any] = {
            "dt_seconds": dt,
            "mode": eng.state.mode,
            "tension": eng.state.tension,
            "curiosite": eng.state.curiosite,
            "decided_action": action.model_dump(),
            "hints": hints,
            "quota_allowed": bool(allowed),
            "quota_denied_reason": deny_reason,
            "meta_before": meta.__dict__,
            "meta_after": meta2.__dict__,
        }
        return nudge, dbg
    return nudge, None

