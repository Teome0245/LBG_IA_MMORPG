"""Postes fixes Garde / Archiviste — anti-murs Mos Eisley."""

from __future__ import annotations

import json
from pathlib import Path


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "content" / "core3" / "core3_npc_catalog.json"


def _entry_by_pilot(catalog: dict, pilot_id: str) -> dict:
    for row in catalog.get("entries") or []:
        if isinstance(row, dict) and row.get("pilot_id") == pilot_id:
            return row
    raise AssertionError(f"missing entry {pilot_id}")


def test_scribe_guard_linger_outdoor_posts():
    cat = json.loads(_catalog_path().read_text(encoding="utf-8"))
    scribe = _entry_by_pilot(cat, "npc:core3_scribe")
    guard = _entry_by_pilot(cat, "npc:core3_guard")
    for entry, x, y in (
        (scribe, 3498, -4788),
        (guard, 3568, -4818),
    ):
        binding = entry["binding"]
        follow = binding["follow_lia"]
        spawn = binding["spawn"]
        assert follow["mode"] == "linger"
        assert int(follow.get("roam_contain_m") or 0) <= 10
        assert int(spawn["x"]) == x
        assert int(spawn["y"]) == y
