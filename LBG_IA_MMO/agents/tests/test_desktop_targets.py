"""Tests routage desktop ciblé par machine."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.desktop_targets import infer_desktop_target_from_text, list_desktop_targets, resolve_desktop_target


def test_list_targets_from_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "LBG_DESKTOP_TARGETS",
        '[{"id":"pc","host":"192.168.0.10","url":"http://192.168.0.10:5005"},'
        '{"id":"ad","host":"192.168.0.100","url":"http://192.168.0.100:5005"}]',
    )
    targets = list_desktop_targets()
    assert len(targets) == 2
    assert {t.target_id for t in targets} == {"pc", "ad"}


def test_resolve_explicit_ad(monkeypatch) -> None:
    monkeypatch.setenv(
        "LBG_DESKTOP_TARGETS",
        '[{"id":"pc","host":"192.168.0.10","url":"http://192.168.0.10:5005"},'
        '{"id":"ad","host":"192.168.0.100","url":"http://192.168.0.100:5005"}]',
    )
    out = resolve_desktop_target({"desktop_target": "ad"}, "")
    assert out is not None
    assert out.target_id == "ad"
    assert out.url == "http://192.168.0.100:5005"
    assert out.source == "explicit"


def test_resolve_from_text_serveur_ad(monkeypatch) -> None:
    monkeypatch.setenv(
        "LBG_DESKTOP_TARGETS",
        '[{"id":"pc","host":"192.168.0.10","url":"http://192.168.0.10:5005"},'
        '{"id":"ad","host":"192.168.0.100","url":"http://192.168.0.100:5005"}]',
    )
    assert infer_desktop_target_from_text("lance notepad sur le serveur ad") == "ad"
    out = resolve_desktop_target({}, "ouvre chrome sur le serveur AD")
    assert out is not None and out.target_id == "ad" and out.source == "text"


def test_dispatch_routes_to_ad_url(monkeypatch) -> None:
    monkeypatch.setenv(
        "LBG_DESKTOP_TARGETS",
        '[{"id":"pc","host":"192.168.0.10","url":"http://192.168.0.10:5005"},'
        '{"id":"ad","host":"192.168.0.100","url":"http://192.168.0.100:5005"}]',
    )
    seen: list[str] = []

    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True, "outcome": "dry_run"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None):
            seen.append(url)
            return FakeResp()

    with patch("lbg_agents.dispatch.httpx.Client", FakeClient):
        from lbg_agents.dispatch import invoke_after_route

        out = invoke_after_route(
            "agent.desktop",
            actor_id="ops:1",
            text="lance notepad sur le serveur ad",
            context={
                "desktop_target": "ad",
                "desktop_action": {"kind": "open_app", "app": "notepad"},
                "desktop_dry_run": True,
            },
        )
    assert seen == ["http://192.168.0.100:5005/invoke"]
    assert out.get("desktop_target") == "ad"
    assert out.get("desktop_target_host") == "192.168.0.100"
