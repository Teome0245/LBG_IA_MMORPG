"""Handlers orchestrateur — capabilities World Director (economy_regulate, world_direct)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from lbg_agents.economy_director import run_economy_director_tick
from lbg_agents.world_chronicler import run_chronicler_tick


def _truthy(raw: object, *, default: bool = True) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _dry_run_from_context(context: dict[str, Any]) -> bool:
    if "world_director_dry_run" in context:
        return _truthy(context.get("world_director_dry_run"), default=True)
    return _truthy(os.environ.get("LBG_WORLD_DIRECTOR_DRY_RUN", "1"), default=True)


def _sidecar_base_url() -> str:
    return os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "").strip().rstrip("/")


def _catalog_path() -> Path:
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_npc_catalog.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_npc_catalog.json")


def pilot_for_roster(roster_id: str, *, catalog: dict[str, Any] | None = None) -> str | None:
    doc = catalog
    if doc is None:
        path = _catalog_path()
        if not path.is_file():
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return None
    for row in doc.get("rosters") or []:
        if not isinstance(row, dict) or str(row.get("roster_id") or "") != roster_id:
            continue
        primary = str(row.get("primary_pilot_id") or "").strip()
        if primary:
            return primary
        slots = row.get("slots") or []
        if slots and isinstance(slots[0], dict):
            return str(slots[0].get("pilot_id") or "").strip() or None
    return None


def apply_world_direct_hints(
    hints: list[dict[str, Any]],
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Enqueue npc_think borné sur le sidecar Prime (hors dry-run)."""
    if dry_run or not hints:
        return []

    base = _sidecar_base_url()
    if not base:
        return [{"ok": False, "error": "LBG_CORE3_IA_SIDECAR_URL non défini"}]

    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(connect=10.0, read=45.0, write=20.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        for hint in hints:
            if not isinstance(hint, dict):
                continue
            roster_id = str(hint.get("roster_id") or "").strip()
            pilot_id = pilot_for_roster(roster_id)
            if not pilot_id:
                results.append({"ok": False, "roster_id": roster_id, "error": "pilot_introuvable"})
                continue
            scene = str(hint.get("scene_profile") or "npc_scene")
            goal_id = str(hint.get("goal_id") or "")
            prompt = (
                f"Objectif monde {goal_id} — joue la scène {scene} pour la faction {hint.get('faction_id')}."
            )
            body = {"pilot_id": pilot_id, "npc_id": pilot_id, "prompt": prompt, "enqueue": True}
            try:
                resp = client.post(f"{base}/v1/npc-think", json=body)
                payload = resp.json() if resp.content else {}
                ok = resp.status_code == 200 and bool(payload.get("ok"))
                results.append(
                    {
                        "ok": ok,
                        "pilot_id": pilot_id,
                        "roster_id": roster_id,
                        "goal_id": goal_id,
                        "sidecar": payload,
                    }
                )
            except httpx.HTTPError as exc:
                results.append({"ok": False, "pilot_id": pilot_id, "error": str(exc)})
    return results


def run_economy_regulate(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    action = context.get("economy_action") if isinstance(context.get("economy_action"), dict) else {}
    dry_run = _dry_run_from_context(context)
    if "dry_run" in action:
        dry_run = _truthy(action.get("dry_run"), default=dry_run)

    stock_overrides = action.get("stock_overrides")
    if not isinstance(stock_overrides, dict):
        stock_overrides = None

    tick = run_economy_director_tick(dry_run=dry_run, stock_overrides=stock_overrides)
    proposed = tick.get("proposed_actions") or []
    lines = [
        f"Économie macro — dry_run={dry_run}",
        f"Signaux : {tick.get('signal_count', 0)} — actions proposées : {len(proposed)}",
    ]
    for row in proposed[:5]:
        if isinstance(row, dict):
            lines.append(f"  • {row.get('action')} ({row.get('shop_id')}) — {row.get('signal')}")
    return {
        "agent": "economy_director",
        "handler": "world_director",
        "actor_id": actor_id,
        "request_text": text,
        "ok": bool(tick.get("ok")),
        "dry_run": dry_run,
        "result": tick,
        "reply": "\n".join(lines),
        "meta": {"capability": "economy_regulate", "read_only": dry_run},
    }


def run_world_direct(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    action = context.get("world_direct_action") if isinstance(context.get("world_direct_action"), dict) else {}
    dry_run = _dry_run_from_context(context)
    if "dry_run" in action:
        dry_run = _truthy(action.get("dry_run"), default=dry_run)

    stock_overrides = action.get("stock_overrides")
    if not isinstance(stock_overrides, dict):
        stock_overrides = None

    tick = run_chronicler_tick(dry_run=dry_run, stock_overrides=stock_overrides)
    hints = tick.get("roster_hints") or []
    enqueued = apply_world_direct_hints(hints, dry_run=dry_run)

    lines = [
        f"Chroniqueur — dry_run={dry_run}",
        f"Objectifs actifs : {tick.get('active_goal_count', 0)} — hints : {len(hints)}",
    ]
    if not dry_run and enqueued:
        lines.append(f"Enqueue sidecar : {sum(1 for r in enqueued if r.get('ok'))}/{len(enqueued)} OK")
    return {
        "agent": "world_chronicler",
        "handler": "world_director",
        "actor_id": actor_id,
        "request_text": text,
        "ok": bool(tick.get("ok")),
        "dry_run": dry_run,
        "result": {**tick, "enqueued": enqueued},
        "reply": "\n".join(lines),
        "meta": {"capability": "world_direct", "read_only": dry_run and not enqueued},
    }
