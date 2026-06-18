"""Pont orchestrateur → sidecar Core3 IA (joueur Lia / PNJ pilotes Phase C)."""

from __future__ import annotations

import os
from typing import Any

import httpx


def _sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "").strip().rstrip("/")


def _sidecar_timeout() -> httpx.Timeout:
    raw = os.environ.get("LBG_CORE3_IA_TIMEOUT", os.environ.get("LBG_AGENT_DIALOGUE_TIMEOUT", "45")).strip()
    try:
        read_s = max(5.0, float(raw))
    except ValueError:
        read_s = 45.0
    return httpx.Timeout(connect=10.0, read=read_s, write=20.0, pool=10.0)


def run_core3_bridge(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    base = _sidecar_base_url()
    if not base:
        return {
            "agent": "core3_dispatch",
            "handler": "core3",
            "actor_id": actor_id,
            "ok": False,
            "outcome": "configuration_error",
            "error": "LBG_CORE3_IA_SIDECAR_URL non défini (ex. http://192.168.0.245:8791).",
        }

    action = context.get("core3_action")
    if not isinstance(action, dict):
        action = {}

    kind = str(action.get("kind") or "npc_think").strip().lower()
    enqueue = action.get("enqueue", True)
    if enqueue is False:
        enqueue = False
    else:
        enqueue = True

    try:
        if kind == "player_think":
            player = str(action.get("player") or os.environ.get("CORE3_IA_BOT_CHARACTER", "Lia")).strip()
            path = "/v1/think"
            body: dict[str, Any] = {
                "prompt": str(action.get("prompt") or text),
                "player": player,
                "enqueue": enqueue,
            }
            if action.get("incarnation") or context.get("lia_incarnation"):
                body["incarnation"] = True
            brain = context.get("orchestrator_brain")
            if isinstance(brain, dict):
                body["orchestrator_brain"] = brain
        elif kind in ("npc_think", "npc_say"):
            npc_id = str(
                action.get("npc_id")
                or action.get("pilot_id")
                or context.get("core3_npc_id")
                or context.get("world_npc_id")
                or ""
            ).strip()
            if not npc_id:
                return {
                    "agent": "core3_dispatch",
                    "handler": "core3",
                    "actor_id": actor_id,
                    "ok": False,
                    "outcome": "bad_request",
                    "error": "npc_id requis (core3_action ou context.core3_npc_id / world_npc_id).",
                }
            path = "/v1/npc-think"
            body = {
                "prompt": str(action.get("prompt") or text),
                "npc_id": npc_id,
                "enqueue": enqueue,
            }
        else:
            return {
                "agent": "core3_dispatch",
                "handler": "core3",
                "actor_id": actor_id,
                "ok": False,
                "outcome": "bad_request",
                "error": f"kind core3_action inconnu : {kind}",
            }

        with httpx.Client(timeout=_sidecar_timeout()) as client:
            resp = client.post(f"{base}{path}", json=body)
        payload = resp.json() if resp.content else {}
        ok = resp.status_code == 200 and bool(payload.get("ok"))
        out = {
            "agent": "core3_dispatch",
            "handler": "core3",
            "actor_id": actor_id,
            "ok": ok,
            "outcome": "ok" if ok else "sidecar_error",
            "http_status": resp.status_code,
            "sidecar": payload,
            "line": payload.get("line"),
            "action": payload.get("action"),
            "pilot_id": payload.get("pilot_id"),
            "observation": payload.get("observation"),
        }
        if ok and (context.get("lia_incarnation") or context.get("core3_autonomy")):
            from lbg_agents.core3_player_events import maybe_apply_social_cooldown

            player_id = str(context.get("core3_player_id") or "lia").strip().lower() or "lia"
            maybe_apply_social_cooldown(player_id, out)
        return out
    except httpx.HTTPError as exc:
        return {
            "agent": "core3_dispatch",
            "handler": "core3",
            "actor_id": actor_id,
            "ok": False,
            "outcome": "sidecar_unreachable",
            "error": str(exc),
        }
