"""Profils comportementaux partagés joueurs IA / PNJ pilotes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def profiles_path() -> Path:
    raw = os.environ.get("LBG_CORE3_BEHAVIOR_PROFILES_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_behavior_profiles.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_behavior_profiles.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_behavior_profiles.json")


def load_behavior_profiles_registry() -> dict[str, Any]:
    path = profiles_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError(f"registre profils comportement invalid: {path}")
    return data


def get_behavior_profile(profile_id: str) -> dict[str, Any]:
    wanted = profile_id.strip()
    profiles = load_behavior_profiles_registry().get("profiles", {})
    if not isinstance(profiles, dict):
        raise KeyError(profile_id)
    row = profiles.get(wanted)
    if not isinstance(row, dict):
        raise KeyError(profile_id)
    return row


def default_profile_for_profession(profession: str) -> str:
    key = profession.strip().lower()
    if key == "scout":
        return "profile:scout_outdoor_v1"
    if key == "artisan":
        return "profile:artisan_gather_v1"
    if key == "entertainer":
        return "profile:entertainer_bar_v1"
    if key == "brawler":
        return "profile:brawler_train_v1"
    if key == "vendor":
        return "profile:cantina_vendor_v1"
    return "profile:entertainer_bar_v1"


def resolve_player_behavior_profile_id(
    *,
    behavior_profile_id: str = "",
    profession_current: str = "",
    role: str = "",
) -> str:
    if behavior_profile_id.strip():
        return behavior_profile_id.strip()
    if role.strip() == "incarnation_orchestrateur":
        return "profile:orchestrator_social_v1"
    return default_profile_for_profession(profession_current)


def _scene_list(profile: dict[str, Any], *, inventory_full: bool = False) -> list[dict[str, Any]]:
    if inventory_full:
        alt = profile.get("scenes_inventory_full")
        if isinstance(alt, list) and alt:
            return [s for s in alt if isinstance(s, dict)]
    scenes = profile.get("scenes")
    if isinstance(scenes, list):
        return [s for s in scenes if isinstance(s, dict)]
    return []


def scene_at_index(
    profile_id: str,
    index: int,
    *,
    inventory_full: bool = False,
) -> dict[str, Any]:
    profile = get_behavior_profile(profile_id)
    scenes = _scene_list(profile, inventory_full=inventory_full)
    if not scenes:
        return {}
    return scenes[index % len(scenes)]


def _scene_id(scene: dict[str, Any]) -> str:
    return str(scene.get("id") or "").strip()


def pick_orchestrator_scene_index(
    profile_id: str,
    index: int,
    *,
    in_interior: bool = False,
    focus_profession: str = "",
) -> int:
    """Rotation cyclique des tours, biaisee par le metier actif du cycle de vie."""
    profile = get_behavior_profile(profile_id)
    scenes = _scene_list(profile)
    if not scenes:
        return 0
    if focus_profession.strip():
        from lbg_agents.core3_profession_lifecycle import load_lifecycle_config, pick_scene_index_for_lifecycle

        return pick_scene_index_for_lifecycle(
            scenes,
            base_index=index,
            focus_profession=focus_profession,
            cfg=load_lifecycle_config(),
        )
    return index % len(scenes)


def pick_player_scene_index(
    profile_id: str,
    index: int,
    *,
    inventory_full: bool = False,
    in_interior: bool = False,
    profession_current: str = "",
    focus_profession: str = "",
) -> int:
    profile = get_behavior_profile(profile_id)
    scenes = _scene_list(profile, inventory_full=inventory_full)
    if not scenes:
        return 0
    n = len(scenes)
    prof = (focus_profession or profession_current).strip().lower() or str(
        profile.get("profession_current") or ""
    ).strip().lower()
    if prof:
        from lbg_agents.core3_profession_lifecycle import load_lifecycle_config, pick_scene_index_for_lifecycle

        return pick_scene_index_for_lifecycle(
            scenes,
            base_index=index,
            focus_profession=prof,
            cfg=load_lifecycle_config(),
        )


def format_scene_hint(
    scene: dict[str, Any],
    channel: str,
    *,
    context: dict[str, str] | None = None,
) -> str:
    """channel: player | npc | orchestrator"""
    key = {"player": "player", "npc": "npc", "orchestrator": "orchestrator"}.get(channel, channel)
    raw = str(scene.get(key) or scene.get("player") or scene.get("npc") or "").strip()
    if not raw:
        return ""
    ctx = context or {}
    try:
        return raw.format(**ctx)
    except KeyError:
        return raw


def build_player_scene_hint(
    profile_id: str,
    index: int,
    *,
    inventory_full: bool = False,
    context: dict[str, str] | None = None,
    in_interior: bool = False,
) -> str:
    prof = get_behavior_profile(profile_id)
    ctx = dict(context or {})
    prof_current = str(ctx.get("profession_current") or prof.get("profession_current") or "")
    focus = str(ctx.get("focus_profession") or prof_current)
    scene_idx = pick_player_scene_index(
        profile_id,
        index,
        inventory_full=inventory_full,
        in_interior=in_interior,
        profession_current=prof_current,
        focus_profession=focus,
    )
    scene = scene_at_index(profile_id, scene_idx, inventory_full=inventory_full)
    ctx.setdefault("profession_secondary", str(prof.get("profession_secondary") or "artisan"))
    return format_scene_hint(scene, "player", context=ctx)


def build_orchestrator_scene_hint(
    profile_id: str,
    index: int,
    *,
    context: dict[str, str] | None = None,
    in_interior: bool = False,
    focus_profession: str = "",
) -> str:
    scene_idx = pick_orchestrator_scene_index(
        profile_id,
        index,
        in_interior=in_interior,
        focus_profession=focus_profession,
    )
    scene = scene_at_index(profile_id, scene_idx)
    return format_scene_hint(scene, "orchestrator", context=context or {})


def build_npc_scene_hint(
    profile_id: str,
    index: int,
    *,
    context: dict[str, str] | None = None,
) -> str:
    scene = scene_at_index(profile_id, index)
    return format_scene_hint(scene, "npc", context=context or {})


def list_npc_autonomy_targets() -> list[dict[str, Any]]:
    """PNJ pilotes avec autonomie active (catalogue Core3)."""
    raw = os.environ.get("LBG_CORE3_NPC_AUTONOMY_PILOTS", "").strip()
    if raw:
        return [{"pilot_id": p.strip()} for p in raw.split(",") if p.strip()]

    catalog_path = Path(
        os.environ.get(
            "CORE3_IA_NPC_CATALOG_JSON",
            "/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json",
        )
    )
    repo_path = Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_npc_catalog.json"
    path = catalog_path if catalog_path.is_file() else repo_path
    if not path.is_file():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_target(pilot_id: str, profile_id: str, interval_s: int) -> None:
        pid = pilot_id.strip()
        if not pid or pid in seen:
            return
        prof = profiles.get(profile_id) if isinstance(profiles, dict) else {}
        if not isinstance(prof, dict):
            return
        if not prof.get("autonomy_enabled"):
            return
        seen.add(pid)
        bp = str(prof.get("behavior_profile_id") or "profile:cantina_vendor_v1").strip()
        out.append(
            {
                "pilot_id": pid,
                "profile_id": profile_id,
                "behavior_profile_id": bp,
                "interval_s": max(60, int(prof.get("autonomy_interval_s") or interval_s or 120)),
            }
        )

    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("pilot_id") or "")
        prof_id = str(entry.get("profile_id") or "")
        add_target(pid, prof_id, int(entry.get("autonomy_interval_s") or 120))

    for roster in data.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        default_prof = str(roster.get("profile_id") or "")
        for slot in roster.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            pid = str(slot.get("pilot_id") or "")
            prof_id = str(slot.get("profile_id") or default_prof)
            if slot.get("autonomy_enabled") is False:
                continue
            add_target(pid, prof_id, int(slot.get("autonomy_interval_s") or 120))

    return out
