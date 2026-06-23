"""Tests quetes et economie joueurs IA."""

from __future__ import annotations

from lbg_agents.core3_economy_loop import pick_economy_step
from lbg_agents.core3_players import get_ai_player
from lbg_agents.core3_profession_lifecycle import ProfessionLifecycleView, tick_player_lifecycle
from lbg_agents.core3_quest_autonomy import (
    GOAL_TO_QUEST,
    deterministic_quest_action,
    pick_quest_for_player,
    template_by_id,
)


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


def test_lia_gather_quest_forages_when_needed(monkeypatch):
    lia = get_ai_player("lia")
    monkeypatch.setattr("lbg_agents.core3_quest_autonomy.active_quest_id", lambda name: "quest:mos_gather_bar_fruit")
    
    snapshot = {"in_interior": False, "inventory_count": 1}
    
    def dummy_enqueue(player, action, message, snapshot, **kwargs):
        return {"action": action, "message": message}
        
    out = deterministic_quest_action(lia, snapshot=snapshot, enqueue=dummy_enqueue)
    assert out is not None
    assert out["action"] == "perform"
    assert out["message"] == "forage"
    assert out["reason"] == "quest_gather_forage"


def test_lia_gather_quest_exits_interior(monkeypatch):
    lia = get_ai_player("lia")
    monkeypatch.setattr("lbg_agents.core3_quest_autonomy.active_quest_id", lambda name: "quest:mos_gather_bar_fruit")
    
    snapshot = {"in_interior": True, "inventory_count": 1}
    
    def dummy_enqueue(player, action, message, snapshot, **kwargs):
        return {"action": action, "message": message}
        
    out = deterministic_quest_action(lia, snapshot=snapshot, enqueue=dummy_enqueue)
    assert out is not None
    assert out["action"] == "move_to"
    assert out["message"] == "mos_eisley_outdoor"
    assert out["reason"] == "quest_gather_exit_interior"


def test_lia_gather_quest_turns_in_when_ready(monkeypatch):
    lia = get_ai_player("lia")
    monkeypatch.setattr("lbg_agents.core3_quest_autonomy.active_quest_id", lambda name: "quest:mos_gather_bar_fruit")
    
    snapshot = {"in_interior": False, "inventory_count": 3}
    
    def dummy_enqueue(player, action, message, snapshot, **kwargs):
        return {"action": action, "message": message}
        
    out = deterministic_quest_action(lia, snapshot=snapshot, enqueue=dummy_enqueue)
    assert out is not None
    assert out["action"] == "interact"
    assert out["message"] == "quest_turnin:Lia:quest:mos_gather_bar_fruit"
    assert out["reason"] == "quest_turnin"


def test_lia_economy_steps():
    lia = get_ai_player("lia")
    life = ProfessionLifecycleView(
        player_id="lia",
        primary="entertainer",
        secondary="artisan",
        phase="learning",
        focus_profession="artisan",
        primary_mastery_pct=100.0,
        secondary_mastery_pct=10.0,
        cycle_index=0,
        forgotten=(),
        prompt_block="",
    )
    
    # 1. Forage: inventory count is 0
    step1 = pick_economy_step(lia, snapshot={"inventory_count": 0}, lifecycle=life)
    assert step1 == "forage"
    
    # 2. Craft: inventory count is 2 and has capability
    step2 = pick_economy_step(lia, snapshot={"inventory_count": 2}, lifecycle=life)
    assert step2 == "craft"

    # 3. Vendor sell: inventory count is full
    step3 = pick_economy_step(lia, snapshot={"inventory_full": True, "inventory_count": 10}, lifecycle=life)
    assert step3 == "vendor_sell"
