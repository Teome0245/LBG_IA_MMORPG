"""Autonomie proactive des PNJ pilotes (profils comportementaux partagés)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from lbg_agents.core3_behavior_profiles import build_npc_scene_hint, list_npc_autonomy_targets
from lbg_agents.core3_player_autonomy import sidecar_base_url

_NPC_TICK: dict[str, int] = {}
_NPC_NEXT: dict[str, float] = {}


def npc_autonomy_enabled() -> bool:
    return os.environ.get("LBG_CORE3_NPC_AUTONOMY_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def npc_autonomy_tick(pilot_id: str, *, behavior_profile_id: str, tick_index: int | None = None) -> dict[str, Any]:
    base = sidecar_base_url()
    if not base:
        return {"ok": False, "outcome": "configuration_error", "pilot_id": pilot_id}

    idx = _NPC_TICK.get(pilot_id, 0) if tick_index is None else tick_index
    _NPC_TICK[pilot_id] = idx + 1
    prompt = build_npc_scene_hint(behavior_profile_id, idx)
    if not prompt:
        prompt = "Une courte replique d'accueil aux voyageurs proches."

    body = {
        "pilot_id": pilot_id,
        "prompt": f"Tour autonome PNJ. Action attendue: {prompt} Reponds via JSON autorise par ton profil.",
        "enqueue": True,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=90.0, write=20.0, pool=10.0)) as client:
            resp = client.post(f"{base}/v1/npc-think", json=body)
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("pilot_id", pilot_id)
        payload.setdefault("behavior_profile_id", behavior_profile_id)
        payload.setdefault("prompt", prompt)
        payload.setdefault("http_status", resp.status_code)
        if resp.status_code == 200 and payload.get("ok"):
            payload["outcome"] = "ok"
        elif resp.status_code == 429:
            payload["outcome"] = "skipped_cooldown"
            payload["ok"] = True
        elif resp.status_code == 409:
            payload["outcome"] = "skipped_offline"
            payload["ok"] = True
        else:
            payload.setdefault("ok", False)
            payload.setdefault("outcome", "npc_think_failed")
        return payload
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "outcome": "sidecar_unreachable",
            "pilot_id": pilot_id,
            "error": str(exc),
        }


def npc_autonomy_tick_all(*, now: float | None = None) -> dict[str, Any]:
    if not npc_autonomy_enabled():
        return {"ok": True, "outcome": "disabled", "npcs": {}}

    mono = time.monotonic()
    now_m = mono if now is None else now
    results: dict[str, Any] = {}
    ok = True
    for target in list_npc_autonomy_targets():
        pid = str(target["pilot_id"])
        interval = float(target.get("interval_s") or 120)
        next_at = _NPC_NEXT.get(pid, 0.0)
        if now_m < next_at:
            results[pid] = {"ok": True, "outcome": "skipped_interval", "next_in_s": round(next_at - now_m, 1)}
            continue
        res = npc_autonomy_tick(pid, behavior_profile_id=str(target["behavior_profile_id"]))
        results[pid] = res
        _NPC_NEXT[pid] = now_m + interval
        if not res.get("ok") and res.get("outcome") not in {"skipped_cooldown", "skipped_offline", "skipped_interval"}:
            ok = False
    return {"ok": ok, "npcs": results}
