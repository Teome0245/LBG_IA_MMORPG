"""Filtre rosters catalogue (exactly_one → un PNJ visible)."""

from __future__ import annotations

from typing import Any


def roster_policies_from_catalog(doc: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for roster in doc.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        rid = str(roster.get("roster_id", "")).strip()
        pol = str(roster.get("service_policy", "")).strip()
        if rid and pol:
            out[rid] = pol
    return out


def allow_roster_npc(
    pilot_id: str,
    meta: dict[str, Any],
    policies: dict[str, str],
    roster_active: dict[str, str],
) -> bool:
    roster_id = str(meta.get("roster_id", "")).strip()
    if policies.get(roster_id) != "exactly_one":
        return True
    if roster_id in roster_active:
        return False
    roster_active[roster_id] = pilot_id
    return True
