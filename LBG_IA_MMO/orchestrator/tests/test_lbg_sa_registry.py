"""Tests registre modules LBG Studios Agents."""

from __future__ import annotations

from lbg_sa.module_registry import get_module, list_modules


def test_list_modules_by_partition() -> None:
    cortex = list_modules(partition="cortex")
    assert any(m.id == "atlas_llm" for m in cortex)
    corps = list_modules(partition="corps")
    assert any(m.id == "player_ia_choeur" for m in corps)
    assert all(m.mmo_safe for m in corps if m.id == "core3_prime")


def test_atlas_module_links_memory_namespace() -> None:
    mod = get_module("atlas_llm")
    assert mod is not None
    assert mod.memory_namespace == "team/atlas"
    assert "110" in mod.host_allowlist


def test_archives_module_present() -> None:
    mod = get_module("lbg_sa_memory")
    assert mod is not None
    assert mod.memory_namespace == "cortex/lbg_sa"
