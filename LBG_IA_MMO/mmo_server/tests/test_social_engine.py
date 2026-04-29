import pytest
from entities.npc import Npc
from lyra_engine.gauges import GaugesState
from simulation.social import SocialEngine
from world.state import WorldState
from entities.location import Location


def test_social_engine_sleep():
    npc = Npc(
        id="npc:test",
        name="Test",
        role="test",
        gauges=GaugesState(fatigue=0.9),
        situation={"location": "work", "housing": "home"},
        goals=["Work hard"]
    )
    world = WorldState(now_s=0, npcs={"npc:test": npc})
    
    engine = SocialEngine(tick_interval_s=10.0)
    
    # Tick below interval does nothing
    engine.step(5.0, world)
    assert npc.situation.get("activity") is None
    
    # Tick crossing the interval triggers the social engine
    engine.step(6.0, world)
    
    # Should be sleeping because fatigue was >= 0.8
    assert npc.situation.get("activity") == "sleeping"
    assert npc.situation.get("location") == "home"
    assert npc.goals == ["Se reposer profondément"]
    
    # Fatigue should be reduced by 0.2
    assert npc.gauges.fatigue == pytest.approx(0.7)


def test_social_engine_eating():
    npc = Npc(
        id="npc:test",
        name="Test",
        role="test",
        gauges=GaugesState(hunger=0.85, fatigue=0.1),
        situation={"location": "work"},
        goals=["Work hard"]
    )
    tavern = Location(id="loc:tavern", name="Tavern", type="building", tags=["tavern"])
    world = WorldState(now_s=0, npcs={"npc:test": npc}, locations={"loc:tavern": tavern})
    
    engine = SocialEngine(tick_interval_s=1.0)
    engine.step(2.0, world)
    
    assert npc.situation.get("activity") == "eating"
    assert npc.situation.get("location") == "loc:tavern"
    assert npc.goals == ["Manger et boire à la taverne"]
    assert npc.gauges.hunger == pytest.approx(0.55)


def test_social_engine_restore_normal():
    npc = Npc(
        id="npc:test",
        name="Test",
        role="test",
        gauges=GaugesState(fatigue=0.1), # recovered
        situation={
            "location": "home", 
            "housing": "home", 
            "activity": "sleeping",
            "default_location": "forge",
            "default_goals": ["Forge things"]
        },
        goals=["Se reposer profondément"]
    )
    world = WorldState(now_s=0, npcs={"npc:test": npc})
    
    engine = SocialEngine(tick_interval_s=1.0)
    engine.step(1.5, world)
    
    # Should restore normal activity
    assert npc.situation.get("activity") == "working"
    assert npc.situation.get("location") == "forge"
    assert npc.goals == ["Forge things"]
    
    # As a side effect of working, fatigue goes up slightly
    assert npc.gauges.fatigue == pytest.approx(0.15)
