"""Tests world_chronicler (faction goals)."""

from __future__ import annotations

from lbg_agents.world_chronicler import (
    evaluate_world_state,
    load_faction_goals,
    run_chronicler_tick,
)


def _economy_low_bar_stock() -> dict:
    return {
        "shops": [
            {
                "shop_id": "shop:mos_cantina_bar",
                "pilot_id": "npc:core3_barman_jax",
                "items": [
                    {"template": "object/tangible/food/foraged/foraged_fruit_s1.iff", "price": 15, "stock": 10},
                ],
            }
        ]
    }


def test_load_faction_goals_has_cantina():
    doc = load_faction_goals()
    factions = doc.get("factions") or []
    ids = [str(f.get("faction_id")) for f in factions if isinstance(f, dict)]
    assert "mos_eisley_cantina" in ids


def test_evaluate_active_goal_when_stock_low():
    active = evaluate_world_state(economy=_economy_low_bar_stock())
    assert any(g.get("goal_id") == "stock_bar" for g in active)
    bar = next(g for g in active if g.get("goal_id") == "stock_bar")
    assert bar.get("roster_id") == "roster:mos_eisley_cantina_barman"


def test_no_goal_when_stock_ok():
    economy = {
        "shops": [
            {
                "shop_id": "shop:mos_cantina_bar",
                "items": [
                    {"template": "object/tangible/food/foraged/foraged_fruit_s1.iff", "stock": 50},
                ],
            }
        ]
    }
    active = evaluate_world_state(economy=economy)
    assert not any(g.get("goal_id") == "stock_bar" for g in active)


def test_chronicler_tick_dry_run():
    out = run_chronicler_tick(dry_run=True, economy=_economy_low_bar_stock())
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["active_goal_count"] >= 1
    assert out["roster_hints"]
