"""
Agent HTTP pour la capability « dialogue » : stub ou LLM (API OpenAI-compatible).

Lancer (venv monorepo) :

    uvicorn lbg_agents.dialogue_http_app:app --host 0.0.0.0 --port 8020

LLM : définir ``LBG_DIALOGUE_LLM_BASE_URL`` (voir ``dialogue_llm``).
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from lbg_agents import dialogue_llm
from lbg_agents import world_content as world_content_mod

app = FastAPI(title="LBG_IA_MMO dialogue HTTP agent", version="0.2.0")

_MAX_PLAYER_CHARS = 400
_MAX_LINE_CHARS = 320


class InvokeIn(BaseModel):
    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _resolve_speaker(ctx: dict[str, object]) -> str:
    for key in ("npc_name", "npc_id", "speaker", "interlocutor"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "PNJ"


def _split_reply_lines(reply: str, *, max_lines: int = 12) -> list[str]:
    parts: list[str] = []
    for block in reply.replace("\r\n", "\n").split("\n"):
        line = block.strip()
        if line:
            parts.append(line[:_MAX_LINE_CHARS])
        if len(parts) >= max_lines:
            break
    if not parts:
        return [reply[:_MAX_LINE_CHARS]]
    return parts


def _stub_turn(player: str, speaker: str) -> tuple[list[str], str]:
    lines = [
        _truncate(
            f"{speaker} — « {player} »… Je vous écoute.",
            _MAX_LINE_CHARS,
        ),
        _truncate(
            f"{speaker} — Configurez LBG_DIALOGUE_LLM_BASE_URL (Ollama, OpenAI, etc.) pour des répliques générées.",
            _MAX_LINE_CHARS,
        ),
    ]
    return lines, "\n\n".join(lines)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    llm_on = dialogue_llm.is_configured()
    desc = (
        "Capability « dialogue » — stub ou LLM (OpenAI-compatible)."
        if llm_on
        else "Capability « dialogue » — mode stub (sans LBG_DIALOGUE_LLM_BASE_URL)."
    )
    out: dict[str, object] = {
        "status": "ok",
        "service": "dialogue_http",
        "title": app.title,
        "version": app.version,
        "invoke": "POST /invoke",
        "description": desc,
        "llm_configured": llm_on,
        "llm_model": dialogue_llm.model_name() if llm_on else None,
        "llm_base_url": dialogue_llm.base_url() if llm_on else None,
        "desktop_plan_env_enabled": dialogue_llm.desktop_plan_env_enabled(),
        "dialogue_budget": dialogue_llm.budget_stats(),
        "dialogue_target_default": os.environ.get("LBG_DIALOGUE_TARGET_DEFAULT", "local").strip().lower(),
        "dialogue_auto_order": os.environ.get("LBG_DIALOGUE_AUTO_ORDER", "local,fast,remote").strip(),
        "cache": dialogue_llm.cache_stats(),
    }
    return out


@app.get("/npc-registry")
def npc_registry(npc_id: str | None = None) -> dict[str, object]:
    """
    Expose le registre PNJ (debug/ops) : utile pour vérifier le contexte injecté dans les prompts.
    - sans param : renvoie la liste
    - avec ?npc_id=npc:... : renvoie l’entrée (ou 404)
    """
    reg = dialogue_llm._load_npc_registry()
    if npc_id:
        rid = npc_id.strip()
        if not rid:
            raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "npc_id vide"})
        entry = reg.get(rid)
        if not isinstance(entry, dict):
            raise HTTPException(status_code=404, detail={"error": "not_found", "npc_id": rid})
        return {"ok": True, "npc": entry}
    rows = list(reg.values())
    try:
        rows.sort(key=lambda x: str(x.get("id", "")))
    except Exception:
        pass
    return {"ok": True, "count": len(rows), "npcs": rows}


@app.get("/world-content")
def world_content() -> dict[str, object]:
    """Inventaire du catalogue monde (races + bestiaire) pour debug / outils."""
    races = world_content_mod.list_race_ids()
    creatures_n = len(world_content_mod.load_creatures_by_id())
    race_display = world_content_mod.race_display_map()
    return {
        "ok": True,
        "races_count": len(races),
        "race_ids": races,
        "creatures_count": creatures_n,
        "race_display": race_display,
    }


def _meta_profile(ctx: dict[str, object]) -> str:
    """Profil dialogue effectif (explicite, registre ``tone``, ou env)."""
    return dialogue_llm._resolve_profile(ctx)


@app.post("/invoke")
def invoke(p: InvokeIn) -> dict[str, object]:
    player = _truncate(p.text, _MAX_PLAYER_CHARS) or "(…)"
    speaker = _resolve_speaker(p.context)
    profile_resolved = _meta_profile(p.context)

    if dialogue_llm.is_configured():
        try:
            if isinstance(p.context, dict):
                p.context["_invoke_actor_id"] = p.actor_id
            reply_text = dialogue_llm.run_dialogue_turn(
                player_text=player,
                speaker=speaker,
                context=p.context,
            )
            lines = _split_reply_lines(reply_text)
            cache_hit = p.context.get("_cache_hit") is True
            world_action = p.context.get("_world_action") if isinstance(p.context, dict) else None
            trace = p.context.get("_dialogue_trace") if isinstance(p.context, dict) else None
            trace_model = trace.get("model") if isinstance(trace, dict) else None
            trace_target = trace.get("target") if isinstance(trace, dict) else None
            desk_prop = p.context.get("_desktop_action_proposal") if isinstance(p.context, dict) else None
            commit = None
            if isinstance(world_action, dict):
                npc_id = (p.context.get("world_npc_id") if isinstance(p.context, dict) else None)
                if world_action.get("kind") == "aid":
                    # Convertir en commit WS borné (les gardes-fous sont aussi côté backend+serveur WS).
                    commit = {
                        "npc_id": npc_id,
                        "flags": {
                            "aid_hunger_delta": world_action.get("hunger_delta", 0.0),
                            "aid_thirst_delta": world_action.get("thirst_delta", 0.0),
                            "aid_fatigue_delta": world_action.get("fatigue_delta", 0.0),
                            "aid_reputation_delta": world_action.get("reputation_delta", 0),
                        },
                    }
                elif world_action.get("kind") == "quest":
                    # Quête : stocker un état minimal côté monde (whitelist côté serveur WS).
                    flags_q: dict[str, object] = {
                        "quest_id": world_action.get("quest_id"),
                        "quest_step": world_action.get("quest_step", 0),
                        "quest_accepted": world_action.get("quest_accepted", True),
                    }
                    if world_action.get("quest_completed") is True:
                        flags_q["quest_completed"] = True
                    rep_raw = world_action.get("reputation_delta", 0)
                    try:
                        rep_i = int(rep_raw)
                    except (TypeError, ValueError):
                        rep_i = 0
                    if rep_i != 0:
                        rep_i = max(-100, min(100, rep_i))
                        flags_q["reputation_delta"] = rep_i
                    pid = world_action.get("player_item_id")
                    if isinstance(pid, str) and pid.strip():
                        flags_q["player_item_id"] = pid.strip()
                        try:
                            qdi = int(world_action.get("player_item_qty_delta", 0))
                        except (TypeError, ValueError):
                            qdi = 0
                        flags_q["player_item_qty_delta"] = qdi
                        plab = world_action.get("player_item_label")
                        if isinstance(plab, str) and plab.strip():
                            flags_q["player_item_label"] = plab.strip()[:80]
                    commit = {
                        "npc_id": npc_id,
                        "flags": flags_q,
                    }
            return {
                "agent": "http_dialogue",
                "reply": reply_text,
                "lines": lines,
                "speaker": speaker,
                "player_text": player,
                "actor_id": p.actor_id,
                "commit": commit,
                "meta": {
                    "stub": False,
                    "llm": True,
                    "model": trace_model if isinstance(trace_model, str) and trace_model.strip() else dialogue_llm.model_name(),
                    "target": trace_target if isinstance(trace_target, str) and trace_target.strip() else None,
                    "agent_version": app.version,
                    "cache_hit": cache_hit,
                    "dialogue_profile_resolved": profile_resolved,
                    "world_action": world_action if isinstance(world_action, dict) else None,
                    "desktop_action_proposal": desk_prop if isinstance(desk_prop, dict) else None,
                    "lyra_engagement_resolved": dialogue_llm.resolve_lyra_engagement(p.context)
                    if isinstance(p.context, dict)
                    else "",
                    "trace": trace,
                },
            }
        except Exception as e:
            lines, reply = _stub_turn(player, speaker)
            return {
                "agent": "http_dialogue",
                "reply": reply,
                "lines": lines,
                "speaker": speaker,
                "player_text": player,
                "actor_id": p.actor_id,
                "meta": {
                    "stub": True,
                    "llm": True,
                    "model": dialogue_llm.model_name(),
                    "llm_error": str(e)[:800],
                    "agent_version": app.version,
                    "cache_hit": False,
                    "dialogue_profile_resolved": profile_resolved,
                },
            }

    lines, reply = _stub_turn(player, speaker)
    return {
        "agent": "http_dialogue",
        "reply": reply,
        "lines": lines,
        "speaker": speaker,
        "player_text": player,
        "actor_id": p.actor_id,
        "meta": {
            "stub": True,
            "llm": False,
            "agent_version": app.version,
            "dialogue_profile_resolved": profile_resolved,
        },
    }


@app.post("/admin/cache/reset")
def admin_cache_reset(
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
) -> dict[str, object]:
    """
    Reset cache mémoire du dialogue (ops/debug).
    Protection optionnelle : si `LBG_DIALOGUE_ADMIN_TOKEN` est défini, il faut passer
    `X-LBG-Service-Token: <token>` (header).
    """
    expected = os.environ.get("LBG_DIALOGUE_ADMIN_TOKEN", "").strip()
    if expected:
        if not (isinstance(x_lbg_service_token, str) and x_lbg_service_token == expected):
            raise HTTPException(
                status_code=401,
                detail={"error": "unauthorized", "hint": "missing/invalid X-LBG-Service-Token"},
            )
    dialogue_llm.reset_cache()
    return {"ok": True, "cache": dialogue_llm.cache_stats()}
