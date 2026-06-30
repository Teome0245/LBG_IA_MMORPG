"""Tests profils comportementaux partagés."""

from lbg_agents.core3_behavior_profiles import (
    build_npc_scene_hint,
    build_orchestrator_scene_hint,
    build_player_scene_hint,
    get_behavior_profile,
    list_npc_autonomy_targets,
    pick_orchestrator_scene_index,
    pick_player_scene_index,
    resolve_player_behavior_profile_id,
)


def test_resolve_lia_orchestrator_profile():
    pid = resolve_player_behavior_profile_id(
        behavior_profile_id="",
        profession_current="entertainer",
        role="incarnation_orchestrateur",
    )
    assert pid == "profile:orchestrator_social_v1"


def test_player_scene_from_scout_profile():
    hint = build_player_scene_hint("profile:scout_outdoor_v1", 0)
    assert "forage" in hint.lower() or "perform" in hint.lower()


def test_orchestrator_scene_has_placeholders_resolved():
    hint = build_orchestrator_scene_hint(
        "profile:orchestrator_social_v1",
        0,
        context={"status": "Relay OK.", "first_online": "Nix"},
    )
    assert "Nix" in hint
    assert "Relay OK" in hint


def test_npc_vendor_profile_scene():
    hint = build_npc_scene_hint("profile:cantina_vendor_v1", 1)
    assert "npc_perform" in hint or "wipe" in hint.lower()


def test_barman_autonomy_target_from_catalog():
    targets = list_npc_autonomy_targets()
    ids = {t["pilot_id"] for t in targets}
    assert "npc:core3_barman_jax" in ids
    row = next(t for t in targets if t["pilot_id"] == "npc:core3_barman_jax")
    assert row["behavior_profile_id"] == "profile:cantina_vendor_v1"


def test_profile_registry_loads():
    prof = get_behavior_profile("profile:entertainer_bar_v1")
    assert prof.get("kind") == "player"
    assert isinstance(prof.get("scenes"), list)


def test_orchestrator_scene_rotates_by_index():
    idx = pick_orchestrator_scene_index("profile:orchestrator_social_v1", 0, in_interior=True)
    hint = build_orchestrator_scene_hint(
        "profile:orchestrator_social_v1",
        idx,
        context={"status": "ok", "first_online": "Nix"},
        in_interior=True,
    )
    assert "Nix" in hint
    assert hint  # scene cyclique, pas uniquement danse


def test_scout_outdoor_prefers_forage():
    idx = pick_player_scene_index(
        "profile:scout_outdoor_v1",
        1,
        in_interior=False,
        profession_current="scout",
    )
    hint = build_player_scene_hint("profile:scout_outdoor_v1", idx, in_interior=False)
    assert "forage" in hint.lower() or "move_to" in hint.lower()
