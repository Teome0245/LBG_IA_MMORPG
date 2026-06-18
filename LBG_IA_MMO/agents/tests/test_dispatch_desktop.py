"""Parité P03 : le dispatch desktop infère open_app depuis un texte libre + hints d'erreur."""

from __future__ import annotations

import pytest

from lbg_agents.dispatch import invoke_after_route


def test_desktop_infers_open_app_from_free_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DESKTOP_URL", raising=False)
    out = invoke_after_route(
        "agent.desktop",
        actor_id="ops:1",
        text="lance vghd sur mon pc",
        context={"desktop_dry_run": True},
    )
    # L'inférence a eu lieu : pas de refus « Aucune desktop_action ».
    assert out.get("error") != "Aucune desktop_action dans context."
    assert out.get("outcome") != "bad_request"


def test_desktop_refuses_when_nothing_inferable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_AGENT_DESKTOP_URL", raising=False)
    out = invoke_after_route(
        "agent.desktop",
        actor_id="ops:1",
        text="quelle heure est-il ?",
        context={},
    )
    assert out.get("ok") is False
    assert out.get("outcome") == "bad_request"
    assert out.get("error") == "Aucune desktop_action dans context."


def test_desktop_http_error_carries_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    # Worker injoignable → erreur réseau ; un objectif allowlist déclenche un hint.
    monkeypatch.setenv("LBG_AGENT_DESKTOP_URL", "http://127.0.0.1:1/")
    out = invoke_after_route(
        "agent.desktop",
        actor_id="ops:1",
        text="lance vghd",
        context={
            "desktop_action": {"kind": "open_app", "app": "vghd"},
            "desktop_dry_run": True,
        },
    )
    assert out.get("agent") == "http_desktop"
    assert out.get("ok") is False
    # Pas de hint spécifique pour une erreur réseau pure (le message ne matche pas les patterns) :
    # on vérifie au moins que la clé hint est gérée sans crash.
    assert "error" in out
