"""
Persistance JSON (phase 2) : commits idempotents et flags PNJ (réconciliation).

Schéma : ``schema_version`` 1 — évolutif.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


def state_to_dict(
    *,
    seen_trace_ids: set[str],
    npc_flags: dict[str, dict[str, Any]],
    npc_reputation: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "seen_trace_ids": sorted(t for t in seen_trace_ids if isinstance(t, str) and t.strip()),
        "npc_flags": npc_flags,
        "npc_reputation": npc_reputation or {},
    }


def state_from_dict(data: dict[str, Any]) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, int]]:
    ver = int(data.get("schema_version", 0))
    if ver not in (1, 2):
        raise ValueError("unsupported schema_version")
    raw_seen = data.get("seen_trace_ids") or []
    if not isinstance(raw_seen, list):
        raise ValueError("seen_trace_ids must be a list")
    seen = {str(x).strip() for x in raw_seen if isinstance(x, (str, int, float)) and str(x).strip()}

    raw_flags = data.get("npc_flags") or {}
    if not isinstance(raw_flags, dict):
        raise ValueError("npc_flags must be a dict")
    npc_flags: dict[str, dict[str, Any]] = {}
    for k, v in raw_flags.items():
        if not isinstance(k, str) or not k.strip():
            continue
        if isinstance(v, dict):
            npc_flags[k.strip()] = v

    rep: dict[str, int] = {}
    if ver >= 2:
        raw_rep = data.get("npc_reputation") or {}
        if isinstance(raw_rep, dict):
            for k, v in raw_rep.items():
                if isinstance(k, str) and k.strip():
                    try:
                        rep[k.strip()] = int(v)
                    except Exception:
                        continue
    return seen, npc_flags, rep


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_state(
    path: Path,
    *,
    seen_trace_ids: set[str],
    npc_flags: dict[str, dict[str, Any]],
    npc_reputation: dict[str, int] | None = None,
) -> None:
    atomic_write_json(
        path,
        state_to_dict(seen_trace_ids=seen_trace_ids, npc_flags=npc_flags, npc_reputation=npc_reputation),
    )


def load_state(path: Path) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, int]] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return state_from_dict(data)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("impossible de charger l’état mmmorpg depuis %s : %s", path, e)
        return None

