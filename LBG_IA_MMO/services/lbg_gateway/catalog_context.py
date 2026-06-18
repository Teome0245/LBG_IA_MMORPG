"""Contexte dialogue IA dérivé du catalogue Core3 (identité PNJ Prime)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_MOBILE_ROLE_FR: dict[str, str] = {
    "bartender": "barman de cantina",
    "trainer_brawler": "instructeur de combat mains nues",
    "trainer_marksman": "instructeur tireur",
    "trainer_scout": "instructeur éclaireur",
    "trainer_medic": "instructeur médecin",
    "trainer_artisan": "instructeur artisan",
    "trainer_entertainer": "instructeur artiste",
    "trainer_politician": "instructeur politique",
    "informant_npc_lvl_1": "informateur",
    "mos_espa_police_officer": "officier de police Mos Eisley",
    "scientist": "scientifique",
    "commoner_old": "habitant",
}


def _load_catalog(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=4)
def _catalog_index(catalog_path: str) -> dict[str, dict[str, Any]]:
    doc = _load_catalog(Path(catalog_path))
    profiles: dict[str, Any] = doc.get("profiles") or {}
    by_pilot: dict[str, dict[str, Any]] = {}

    for roster in doc.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        roster_desc = str(roster.get("description", "")).strip()
        roster_loc = str(roster.get("location_id", "")).strip()
        roster_profile_id = str(roster.get("profile_id", "")).strip()
        roster_profile = profiles.get(roster_profile_id) if roster_profile_id else {}
        if not isinstance(roster_profile, dict):
            roster_profile = {}

        for slot in roster.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            pid = str(slot.get("pilot_id", "")).strip()
            if not pid:
                continue
            binding = slot.get("binding") or {}
            mobile = str(binding.get("mobile_template", "")).strip()
            role_fr = _MOBILE_ROLE_FR.get(mobile, str(roster_profile.get("role", "citoyen")))
            prof_id = str(slot.get("profile_id", roster_profile_id)).strip()
            prof = profiles.get(prof_id) if prof_id else roster_profile
            if not isinstance(prof, dict):
                prof = roster_profile
            llm = prof.get("llm") if isinstance(prof.get("llm"), dict) else {}
            hint = str(llm.get("system_hint", "")).strip()

            by_pilot[pid] = {
                "pilot_id": pid,
                "display_name": str(slot.get("display_name", pid)).strip(),
                "role_fr": role_fr,
                "mobile_template": mobile,
                "roster_id": str(roster.get("roster_id", "")).strip(),
                "location_id": roster_loc,
                "roster_description": roster_desc,
                "profile_id": prof_id,
                "llm_system_hint": hint,
            }
    return by_pilot


def build_dialogue_context(
    pilot_id: str,
    *,
    catalog_path: Path,
    npc_name: str | None = None,
) -> dict[str, Any]:
    """Enrichit le contexte orchestrateur pour éviter les confusions de métier (Terre1 / fantasy)."""
    pid = pilot_id.strip()
    idx = _catalog_index(str(catalog_path.resolve()))
    meta = idx.get(pid, {})
    name = (npc_name or meta.get("display_name") or pid).strip()

    ctx: dict[str, Any] = {
        "world_npc_id": pid,
        "history": [],
        "lyra_engagement": "mmo_persona",
        "planet_id": "tatooine",
        "zone": "mos_eisley",
    }
    if name:
        ctx["npc_name"] = name

    if not meta:
        ctx["session_summary"] = {
            "last_npc": f"{name} ({pid})",
            "memory_hint": "Serveur Core3 Prime Tatooine — rester cohérent SWG, pas village fantasy Terre1.",
        }
        return ctx

    role_fr = str(meta.get("role_fr", "citoyen"))
    loc = str(meta.get("location_id", "tatooine")).replace("_", " ")
    roster = str(meta.get("roster_description", "")).strip()
    hint = str(meta.get("llm_system_hint", "")).strip()

    identity = f"{name} — {role_fr}, Mos Eisley ({loc})"
    if roster:
        identity += f" ; {roster[:120]}"

    memory_parts = [
        f"Identité fixe: tu es {name}, {role_fr} sur Tatooine Prime (Core3).",
        "Interdit: forgeron, artisan du village, aubergiste Terre1, marchande fantasy, ou autre métier non listé.",
        f"pilot_id={pid}",
    ]
    if hint:
        memory_parts.append(f"Consigne métier: {hint[:400]}")

    ctx["session_summary"] = {
        "last_npc": identity,
        "memory_hint": " ".join(memory_parts),
        "session_mood": "cantina_mos_eisley" if "cantina" in loc or "barman" in role_fr else "tatooine_prime",
    }
    return ctx
