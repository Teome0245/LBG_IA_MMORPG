"""Validation catalogue — Jax cantina + instructeur artisan (Track E)."""

from __future__ import annotations

import json
from pathlib import Path

from lbg_agents.core3_behavior_profiles import list_npc_autonomy_targets


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "content" / "core3" / "core3_npc_catalog.json"


def _load_catalog() -> dict:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


def _roster_by_id(catalog: dict, roster_id: str) -> dict | None:
    for row in catalog.get("rosters") or []:
        if isinstance(row, dict) and row.get("roster_id") == roster_id:
            return row
    return None


def test_jax_in_cantina_roster_active():
    cat = _load_catalog()
    roster = _roster_by_id(cat, "roster:mos_eisley_cantina_barman")
    assert roster is not None
    assert roster.get("status") == "active"
    assert roster.get("primary_pilot_id") == "npc:core3_barman_jax"
    slots = roster.get("slots") or []
    jax = next((s for s in slots if s.get("pilot_id") == "npc:core3_barman_jax"), None)
    assert jax is not None
    assert jax.get("profile_id") == "profile:cantina_barman_mos_v1"
    prof = cat["profiles"]["profile:cantina_barman_mos_v1"]
    assert prof.get("autonomy_enabled") is True


def test_artisan_trainer_roster_active():
    cat = _load_catalog()
    roster = _roster_by_id(cat, "roster:mos_trainer_artisan")
    assert roster is not None
    assert roster.get("status") == "active"
    post = roster.get("service_post") or {}
    assert int(post.get("cell") or 0) == 1189639
    slots = roster.get("slots") or []
    lead = next((s for s in slots if s.get("pilot_id") == "npc:core3_artisan_trainer_a"), None)
    assert lead is not None
    assert lead.get("profile_id") == "profile:trainer_artisan_mos_v1"
    prof = cat["profiles"]["profile:trainer_artisan_mos_v1"]
    assert prof.get("autonomy_enabled") is True
    assert prof.get("behavior_profile_id") == "profile:trainer_artisan_v1"


def test_autonomy_targets_include_jax_or_artisan_winner():
    targets = list_npc_autonomy_targets()
    pilot_ids = {t["pilot_id"] for t in targets}
    assert "npc:core3_barman_jax" in pilot_ids or "npc:core3_artisan_trainer_a" in pilot_ids
