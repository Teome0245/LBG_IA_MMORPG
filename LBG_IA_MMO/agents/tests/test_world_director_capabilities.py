"""Tests capabilities World Director (economy_regulate, world_direct)."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.dispatch import invoke_after_route
from lbg_agents.world_director_capabilities import (
    apply_world_direct_hints,
    pilot_for_roster,
    run_economy_regulate,
    run_world_direct,
)


def test_pilot_for_roster_uses_primary():
    pid = pilot_for_roster("roster:mos_eisley_cantina_barman")
    assert pid == "npc:core3_barman_jax"


def test_economy_regulate_dry_run():
    out = run_economy_regulate(actor_id="ops", text="tick économie", context={})
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["meta"]["capability"] == "economy_regulate"
    assert "result" in out


def test_world_direct_dry_run_no_enqueue():
    out = run_world_direct(
        actor_id="ops",
        text="chroniqueur",
        context={"world_direct_action": {"stock_overrides": {"shop:mos_cantina_bar:object/tangible/food/foraged/foraged_fruit_s1.iff": 5}}},
    )
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["result"]["active_goal_count"] >= 1
    assert out["result"]["enqueued"] == []


def test_apply_world_direct_hints_skips_when_dry_run():
    hints = [{"roster_id": "roster:mos_eisley_cantina_barman", "goal_id": "stock_bar"}]
    assert apply_world_direct_hints(hints, dry_run=True) == []


def test_dispatch_economy_regulate_route():
    out = invoke_after_route(
        "agent.economy",
        actor_id="test",
        text="réguler économie",
        context={"economy_action": {"dry_run": True}},
    )
    assert out["agent"] == "economy_director"
    assert out["ok"] is True


def test_dispatch_world_direct_route():
    with patch("lbg_agents.world_director_capabilities.apply_world_direct_hints", return_value=[]):
        out = invoke_after_route(
            "agent.chronicler",
            actor_id="test",
            text="diriger monde",
            context={"world_direct_action": {"dry_run": True}},
        )
    assert out["agent"] == "world_chronicler"
    assert out["ok"] is True
