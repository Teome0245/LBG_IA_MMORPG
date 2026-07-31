"""Tests alertes Element périmètre Atlas."""

from __future__ import annotations

from team.admin_infra_element import (
    format_perimeter_ko_message,
    perimeter_has_ko,
    perimeter_ko_signature,
    should_send_perimeter_alert,
)


def test_perimeter_has_ko_from_hosts_count() -> None:
    assert perimeter_has_ko({"hosts_ok": 3, "hosts_total": 4, "gaps": []})
    assert not perimeter_has_ko({"hosts_ok": 4, "hosts_total": 4, "gaps": []})


def test_signature_changes_when_failed_host_changes() -> None:
    p1 = {
        "hosts": [{"ok": False, "perimeter_id": "245", "id": "precu_245"}],
        "gaps": [],
    }
    p2 = {
        "hosts": [{"ok": False, "perimeter_id": "246", "id": "prime_246"}],
        "gaps": [],
    }
    assert perimeter_ko_signature(p1) != perimeter_ko_signature(p2)


def test_should_send_when_signature_new() -> None:
    platform = {
        "hosts_ok": 3,
        "hosts_total": 4,
        "perimeter": ["110", "140", "245", "246"],
        "hosts": [
            {"ok": True, "perimeter_id": "110", "label": "a", "host": "1.1.1.1"},
            {"ok": False, "perimeter_id": "245", "label": "b", "host": "2.2.2.2", "probes": []},
        ],
        "gaps": [],
    }
    assert should_send_perimeter_alert(platform, state={})
    msg = format_perimeter_ko_message(platform)
    assert "245" in msg
    assert "KO" in msg
