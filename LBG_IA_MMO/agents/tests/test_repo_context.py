"""Tests repo_context."""

from __future__ import annotations

import pathlib

from lbg_agents import repo_context


def test_grep_repo_finds_pattern(tmp_path: pathlib.Path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("pilot_chat endpoint\n", encoding="utf-8")
    monkeypatch.setenv("LBG_REPO_ROOT", str(tmp_path))
    hits = repo_context.grep_repo("pilot_chat")
    assert any(h.get("file") == "docs/note.md" for h in hits)


def test_build_tree_summary(tmp_path: pathlib.Path, monkeypatch) -> None:
    (tmp_path / "pilot_shell").mkdir()
    (tmp_path / "README.md").write_text("# test", encoding="utf-8")
    monkeypatch.setenv("LBG_REPO_ROOT", str(tmp_path))
    tree = repo_context.build_tree_summary()
    assert "pilot_shell/" in tree
    assert "README.md" in tree
