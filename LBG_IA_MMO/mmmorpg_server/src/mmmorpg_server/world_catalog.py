"""Lecture du catalogue races pour enrichir les snapshots (même JSON que les agents)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_races_by_id: dict[str, dict[str, Any]] | None = None


def reset_races_cache() -> None:
    global _races_by_id
    _races_by_id = None


def _content_dir() -> Path:
    # mmmorpg_server/world_catalog.py -> parents[3] = LBG_IA_MMO
    return Path(__file__).resolve().parents[3] / "content" / "world"


def load_races_by_id() -> dict[str, dict[str, Any]]:
    global _races_by_id
    if _races_by_id is not None:
        return _races_by_id
    path = _content_dir() / "races.json"
    out: dict[str, dict[str, Any]] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _races_by_id = out
        return out
    rows = data.get("races") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _races_by_id = out
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if isinstance(rid, str) and rid.strip():
            out[rid.strip()] = row
    _races_by_id = out
    return out


def race_display_name(race_id: str) -> str:
    rid = (race_id or "").strip()
    if not rid:
        return ""
    m = load_races_by_id().get(rid)
    if not isinstance(m, dict):
        return rid
    dn = m.get("display_name")
    return dn.strip() if isinstance(dn, str) and dn.strip() else rid
