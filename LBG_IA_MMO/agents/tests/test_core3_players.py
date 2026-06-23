"""Tests registre joueurs IA Core3."""

from lbg_agents.core3_players import get_ai_player, list_ai_players, player_prompt_context


def test_list_ai_players_contains_lia_and_nix():
    players = list_ai_players()
    ids = {p.id for p in players}
    assert {"lia", "nix"} <= ids


def test_get_nix_by_firstname():
    nix = get_ai_player("Nix")
    assert nix.account == "Bot_IA_2"
    assert nix.profession_current == "scout"
    assert nix.behavior_profile_id == "profile:scout_outdoor_v1"
    assert nix.profession_dynamic is True
    assert "forage" in nix.capabilities


def test_mira_registered_pending_character_oid():
    mira = get_ai_player("mira")
    assert mira.enabled is True
    assert mira.account == "Bot_IA_3"
    assert mira.behavior_profile_id == "profile:artisan_gather_v1"


def test_prompt_context_mentions_dynamic_profession():
    ctx = player_prompt_context(get_ai_player("lia"))
    assert "métier courant" in ctx
    assert "capabilities" in ctx
