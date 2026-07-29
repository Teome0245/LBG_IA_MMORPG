"""Tests mémoire LBG Studios Agents (LBG_SA)."""

from __future__ import annotations

import pytest

from lbg_sa.memory_store import LbgSaMemoryStore, get_memory_store, memory_root, reset_memory_cache_for_tests


@pytest.fixture(autouse=True)
def _isolate_memory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_memory_cache_for_tests()
    monkeypatch.setenv("LBG_TEAM_DB_PATH", str(tmp_path / "team_tasks.db"))
    monkeypatch.setenv("LBG_STUDIOS_AGENTS_MEMORY_ROOT", str(tmp_path / "lbg-sa-memory"))
    monkeypatch.setenv("LBG_STUDIOS_AGENTS_MEMORY_ENABLED", "1")


def test_memory_root_follows_team_db_parent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_STUDIOS_AGENTS_MEMORY_ROOT", raising=False)
    monkeypatch.delenv("LBG_SA_MEMORY_ROOT", raising=False)
    db = tmp_path / "nested" / "team_tasks.db"
    monkeypatch.setenv("LBG_TEAM_DB_PATH", str(db))
    root = memory_root()
    assert root == tmp_path / "nested" / "lbg_sa" / "memory"


def test_memory_root_accepts_lbg_sa_alias(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_STUDIOS_AGENTS_MEMORY_ROOT", raising=False)
    monkeypatch.setenv("LBG_SA_MEMORY_ROOT", str(tmp_path / "alias-mem"))
    assert memory_root() == tmp_path / "alias-mem"


def test_append_and_recall_namespace() -> None:
    store = LbgSaMemoryStore("team/atlas")
    store.append_learning("Bench stabilise 4/6 sur gemma4:e2b", tags=["bench", "atlas"])
    hits = store.recall("bench gemma4", limit=3)
    assert hits
    assert "4/6" in hits[0].summary
    path = store.path()
    assert path is not None
    assert path.is_file()


def test_get_memory_store_caches_per_namespace() -> None:
    a = get_memory_store("team/atlas")
    b = get_memory_store("team/atlas")
    assert a is b
    c = get_memory_store("player/lia")
    assert c is not a


def test_invalid_namespace_raises() -> None:
    with pytest.raises(ValueError):
        LbgSaMemoryStore("INVALID NAMESPACE")
