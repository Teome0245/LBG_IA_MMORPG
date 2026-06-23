"""Starport pilots — postes outdoor (evite PNJ dans les murs cantina)."""

from __future__ import annotations

import json
from pathlib import Path


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "content" / "core3" / "core3_npc_catalog.json"


def _load_catalog() -> dict:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


def _roster_by_id(catalog: dict, roster_id: str) -> dict | None:
    for row in catalog.get("rosters") or []:
        if isinstance(row, dict) and row.get("roster_id") == roster_id:
            return row
    return None


def test_starport_pilot_posts_are_outdoor_and_away_from_cantina_entrance():
    cat = _load_catalog()
    cantina_entrance = (3528, -4804)
    for roster_id in (
        "roster:mos_pilot_alliance",
        "roster:mos_pilot_imperial",
        "roster:mos_pilot_freelance",
    ):
        roster = _roster_by_id(cat, roster_id)
        assert roster is not None, roster_id
        post = roster.get("service_post") or {}
        assert int(post.get("cell") or 0) == 0
        px, py = float(post["x"]), float(post["y"])
        dist = ((px - cantina_entrance[0]) ** 2 + (py - cantina_entrance[1]) ** 2) ** 0.5
        assert dist >= 25, f"{roster_id} trop proche cantina ({px},{py}) dist={dist:.1f}"


def test_starport_relief_slots_include_theo_mord_dorn():
    cat = _load_catalog()
    names = {}
    for roster_id, pilot_id in (
        ("roster:mos_pilot_alliance", "npc:core3_pilot_alliance_c"),
        ("roster:mos_pilot_imperial", "npc:core3_pilot_imperial_c"),
        ("roster:mos_pilot_freelance", "npc:core3_pilot_freelance_c"),
    ):
        roster = _roster_by_id(cat, roster_id)
        assert roster is not None
        slot = next(s for s in roster["slots"] if s["pilot_id"] == pilot_id)
        names[pilot_id] = slot["display_name"]
    assert names["npc:core3_pilot_alliance_c"] == "Theo Nash"
    assert names["npc:core3_pilot_imperial_c"] == "Mord Kael"
    assert names["npc:core3_pilot_freelance_c"] == "Dorn Pike"
