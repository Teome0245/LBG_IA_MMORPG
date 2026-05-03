"""Tests action desktop mail_imap_preview (exécuteur local)."""

from __future__ import annotations

import os

import pytest

from lbg_agents.desktop_executor import run_desktop_action
from lbg_agents.dialogue_llm import _sanitize_desktop_action_proposal


def test_mail_imap_preview_disabled_by_default() -> None:
    os.environ.pop("LBG_DESKTOP_MAIL_ENABLED", None)
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "mail_imap_preview", "from_contains": "intel"},
        context={"desktop_dry_run": True},
    )
    assert out["outcome"] == "feature_disabled"
    assert out.get("ok") is False


def test_mail_imap_preview_bad_request_no_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_MAIL_ENABLED", "1")
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "mail_imap_preview"},
        context={"desktop_dry_run": True},
    )
    assert out["outcome"] == "bad_request"


def test_mail_imap_preview_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_MAIL_ENABLED", "1")
    monkeypatch.setenv("LBG_DESKTOP_DRY_RUN", "1")
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "mail_imap_preview", "from_contains": "Intel", "subject_contains": "offre"},
        context={},
    )
    assert out["outcome"] == "dry_run"
    assert out.get("ok") is True
    msgs = out.get("messages")
    assert isinstance(msgs, list) and len(msgs) == 1
    assert "intel" in (msgs[0].get("subject") or "").lower()


def test_mail_imap_preview_configuration_error_when_not_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_MAIL_ENABLED", "1")
    monkeypatch.setenv("LBG_DESKTOP_DRY_RUN", "0")
    for k in (
        "LBG_DESKTOP_MAIL_IMAP_HOST",
        "LBG_DESKTOP_MAIL_IMAP_USER",
        "LBG_DESKTOP_MAIL_IMAP_PASSWORD",
    ):
        monkeypatch.delenv(k, raising=False)
    out = run_desktop_action(
        actor_id="a",
        text="t",
        action={"kind": "mail_imap_preview", "from_contains": "x"},
        context={},
    )
    assert out["outcome"] == "configuration_error"
    assert out.get("ok") is False


def test_sanitize_desktop_mail_proposal() -> None:
    s = _sanitize_desktop_action_proposal(
        {"kind": "mail_imap_preview", "from_contains": "bob", "max_messages": 99}
    )
    assert s is not None
    assert s["kind"] == "mail_imap_preview"
    assert s["from_contains"] == "bob"
    assert s["max_messages"] == 10


def test_sanitize_desktop_mail_rejects_empty_filters() -> None:
    assert _sanitize_desktop_action_proposal({"kind": "mail_imap_preview"}) is None
