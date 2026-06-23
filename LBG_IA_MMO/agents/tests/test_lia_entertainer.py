"""Tests playbook entertainer Lia."""

from __future__ import annotations

from lbg_agents.lia_entertainer import (
    dances_for_tier,
    load_playbook,
    macro_slots,
    suggest_entertainer_action,
)


def test_playbook_loads():
    pb = load_playbook()
    assert pb.get("schema_version") == 1
    assert "F1" in macro_slots()
    assert macro_slots()["F4"]["perform"] == "dance:formal"


def test_dances_per_tier():
    assert "basic" in dances_for_tier(0)
    assert "formal" in dances_for_tier(1)


def test_dances_cumulative():
    from lbg_agents.lia_entertainer import dances_unlocked_cumulative

    d = dances_unlocked_cumulative(2)
    assert "basic" in d
    assert "formal" in d
    assert "popular" in d
    assert "exotic" not in d


def test_suggest_training_when_learning():
    act = suggest_entertainer_action(
        lifecycle_phase="learning",
        mastery_pct=50,
        in_cantina=True,
        in_training=False,
        current_tier=0,
    )
    assert act is not None
    assert act["action"] == "housing_enter"
    assert act["message"] == "training"


def test_suggest_learn_at_trainer():
    act = suggest_entertainer_action(
        lifecycle_phase="learning",
        mastery_pct=50,
        in_cantina=False,
        in_training=True,
        current_tier=1,
    )
    assert act == {"action": "learn_entertainer", "message": "trainer"}
