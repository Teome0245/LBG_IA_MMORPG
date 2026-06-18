"""Tests economy_director (macro)."""

from __future__ import annotations

from lbg_agents.economy_director import (
    collect_shop_signals,
    evaluate_rules,
    propose_actions,
    run_economy_director_tick,
)


def _mini_economy() -> dict:
    return {
        "shops": [
            {
                "shop_id": "shop:mos_cantina_bar",
                "pilot_id": "npc:core3_barman_jax",
                "items": [
                    {"template": "object/tangible/food/foraged/foraged_fruit_s1.iff", "price": 15, "stock": 3},
                    {"template": "object/tangible/food/foraged/foraged_fruit_s2.iff", "price": 25, "stock": 40},
                ],
            },
            {
                "shop_id": "shop:mos_scribe_supplies",
                "pilot_id": "npc:core3_scribe",
                "items": [
                    {"template": "object/tangible/food/foraged/foraged_fruit_s1.iff", "price": 25, "stock": 20},
                ],
            },
        ]
    }


def test_collect_shop_signals():
    signals = collect_shop_signals(_mini_economy())
    assert len(signals) == 3
    assert signals[0]["shop_id"] == "shop:mos_cantina_bar"


def test_evaluate_rules_scarcity():
    signals = collect_shop_signals(_mini_economy())
    ev = evaluate_rules(signals, rules={"stock_low_threshold": 15, "stock_critical_threshold": 5})
    critical = [e for e in ev if e.get("signal") == "resource_scarcity"]
    assert critical
    assert critical[0]["stock"] == 3


def test_propose_quest_on_scarcity():
    signals = collect_shop_signals(_mini_economy())
    ev = evaluate_rules(signals, rules={"stock_low_threshold": 15, "stock_critical_threshold": 5})
    actions = propose_actions(ev)
    assert any(a.get("action") == "offer_quest" for a in actions)
    quest = next(a for a in actions if a.get("action") == "offer_quest")
    assert quest.get("quest_id") == "quest:mos_gather_bar_fruit"
    assert quest.get("giver_pilot_id") == "npc:core3_barman_jax"


def test_run_tick_dry_run():
    out = run_economy_director_tick(dry_run=True, economy=_mini_economy())
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["signal_count"] == 3
    assert isinstance(out["proposed_actions"], list)


def test_empty_economy_config():
    out = run_economy_director_tick(dry_run=True, economy={})
    assert out["ok"] is True
    assert out["signal_count"] == 0
    assert out["proposed_actions"] == []
