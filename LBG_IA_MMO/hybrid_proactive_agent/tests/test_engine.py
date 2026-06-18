from __future__ import annotations

import json
from pathlib import Path

from hybrid_proactive_agent import (
    HybridProactiveEngine,
    LongTermMemoryStore,
    MemoryEntry,
    MultiAgentProactiveCoordinator,
    SpecialistRole,
    integration_hints,
    team_integration_hints,
)


def test_mode_autonome_when_tension_high() -> None:
    eng = HybridProactiveEngine(tension_autonome_seuil=0.5)
    eng.state.tension = 0.7
    assert eng.choose_mode({}) == "autonome"
    action = eng.decide({})
    assert action.mode == "autonome"
    assert action.kind.value == "autonomous_nudge"


def test_mode_avance_when_missing_info_and_curiosity() -> None:
    eng = HybridProactiveEngine()
    eng.observe_user_turn("c'est un peu flou pour moi", {"intent": "build_bot"})
    assert eng.choose_mode({"missing_info": True}) in ("proactif_avance", "autonome")


def test_integration_hints_contains_keys() -> None:
    eng = HybridProactiveEngine()
    eng.state.mode = "proactif_avance"
    hints = integration_hints(eng.state, {"npc_id": "npc:lyra", "session_id": "s1"})
    assert hints["hybrid_proactive_mode"] == "proactif_avance"
    assert hints["mmo_npc_id"] == "npc:lyra"


def test_long_term_memory_recall(tmp_path: Path) -> None:
    p = tmp_path / "mem.jsonl"
    mem = LongTermMemoryStore(path=p, max_entries=100)
    mem.append(MemoryEntry(summary="L'utilisateur veut un agent proactif en Python", tags=["prefs", "stack"]))
    mem.append(MemoryEntry(summary="Préférence : zéro exécution sans validation", tags=["policy"]))
    hits = mem.recall("python agent", limit=2)
    assert hits
    assert "Python" in hits[0].summary or "python" in hits[0].summary.lower()


def test_multi_agent_coordinator_picks_strongest_mode() -> None:
    coord = MultiAgentProactiveCoordinator()
    coord.observe_all("je ne sais pas encore", {"intent": None})
    coord.set_active_role(SpecialistRole.GAME_DESIGNER)
    role, action = coord.decide_with_memory({"objectif_flou": True})
    assert role in coord.engines
    assert action.mode in ("proactif_leger", "proactif_avance", "autonome")


def test_team_integration_hints() -> None:
    coord = MultiAgentProactiveCoordinator()
    coord.set_active_role(SpecialistRole.ARCHITECTE)
    h = team_integration_hints(coord, {})
    assert h.get("active_specialist") == SpecialistRole.ARCHITECTE


def test_jsonl_persistence_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "m.jsonl"
    m1 = LongTermMemoryStore(path=p)
    m1.append(MemoryEntry(summary="alpha", tags=["t1"]))
    m2 = LongTermMemoryStore(path=p)
    assert len(m2._entries) >= 1
    first_line = p.read_text(encoding="utf-8").strip().splitlines()[0]
    raw = json.loads(first_line)
    assert raw["summary"] == "alpha"
