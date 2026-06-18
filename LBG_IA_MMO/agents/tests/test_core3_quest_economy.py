"""Tests quetes et economie joueurs IA."""

from __future__ import annotations

from lbg_agents.core3_economy_loop import pick_economy_step
from lbg_agents.core3_players import get_ai_player
from lbg_agents.core3_profession_lifecycle import ProfessionLifecycleView, tick_player_lifecycle
from lbg_agents.core3_quest_autonomy import GOAL_TO_QUEST, pick_quest_for_player, template_by_id


def test_lia_quest_maps_from_progression_goals():
    lia = get_ai_player("lia")
    qid = pick_quest_for_player(lia)
    assert qid is not None
    assert qid.startswith("quest:")
    tpl = template_by_id(qid)
    assert tpl is not None


def test_goal_maps_to_quest_template():
    nix = get_ai_player("nix")
    qid = pick_quest_for_player(nix)
    assert qid in GOAL_TO_QUEST.values()


def test_economy_forage_when_learning_scout():
    nix = get_ai_player("nix")
    life = tick_player_lifecycle(nix, activity=False, persist=False)
    step = pick_economy_step(nix, snapshot={"in_interior": False, "inventory_count": 2}, lifecycle=life)
    assert step in {"forage", "craft", "vendor_sell", "trainer"}


def test_economy_vendor_sell_when_inventory_full():
    mira = get_ai_player("mira")
    life = ProfessionLifecycleView(
        player_id="mira",
        primary="artisan",
        secondary="entertainer",
        phase="learning",
        focus_profession="artisan",
        primary_mastery_pct=10,
        secondary_mastery_pct=0,
        cycle_index=0,
        forgotten=(),
        prompt_block="",
    )
    step = pick_economy_step(
        mira,
        snapshot={"inventory_full": True, "inventory_count": 10},
        lifecycle=life,
    )
    assert step == "vendor_sell"
