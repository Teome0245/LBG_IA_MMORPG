"""Tests action desktop search_web_open (exécuteur local)."""

from __future__ import annotations

import os

import pytest

from lbg_agents.desktop_executor import run_desktop_action


def test_search_web_open_disabled_by_default() -> None:
    os.environ.pop("LBG_DESKTOP_WEB_SEARCH", None)
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "search_web_open", "query": "hello"},
        context={"desktop_dry_run": True},
    )
    assert out["outcome"] == "feature_disabled"
    assert out.get("ok") is False


def test_search_web_open_dry_run_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_WEB_SEARCH", "1")
    monkeypatch.setenv("LBG_DESKTOP_DRY_RUN", "1")
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "search_web_open", "query": "exemple recherche"},
        context={},
    )
    assert out["outcome"] == "dry_run"
    assert out.get("ok") is True
    url = out.get("url")
    assert isinstance(url, str)
    assert "duckduckgo.com" in url
    assert "exemple" in url or "exemple+recherche" in url or "exemple%20recherche" in url


def test_search_web_open_google_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_WEB_SEARCH", "1")
    monkeypatch.setenv("LBG_DESKTOP_DRY_RUN", "1")
    monkeypatch.setenv("LBG_DESKTOP_SEARCH_ENGINE", "google")
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "search_web_open", "query": "foo"},
        context={},
    )
    assert out["outcome"] == "dry_run"
    u = str(out.get("url"))
    assert "google.com/search" in u
