"""Tests action desktop open_url (exécuteur local, dry-run)."""

from __future__ import annotations

import pytest

from lbg_agents.desktop_executor import run_desktop_action


def test_open_url_allowlist_denied_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DESKTOP_URL_ALLOWLIST", raising=False)
    monkeypatch.delenv("LBG_DESKTOP_URL_HOST_ALLOWLIST", raising=False)
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "open_url", "url": "https://example.org/"},
        context={"desktop_dry_run": True},
    )
    assert out.get("ok") is False
    assert out.get("outcome") == "allowlist_denied"


def test_open_url_dry_run_with_host_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_URL_HOST_ALLOWLIST", "example.org")
    monkeypatch.delenv("LBG_DESKTOP_DRY_RUN", raising=False)
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "open_url", "url": "https://example.org/foo"},
        context={"desktop_dry_run": True},
    )
    assert out.get("ok") is True
    assert out.get("outcome") == "dry_run"
    assert out.get("url") == "https://example.org/foo"
