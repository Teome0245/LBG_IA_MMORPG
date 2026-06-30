"""Tests sonde stockage Proxmox (pool thin local-lvm, multi-PVE)."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.infra_storage_remediation import build_storage_remediation_plan
from lbg_agents.proxmox_storage_probe import (
    _aggregate_host_probes,
    format_storage_probe_reply,
    probe_proxmox_storage_host,
    probe_proxmox_storage_local,
    thin_crit_pct,
    thin_warn_pct,
)


def test_probe_warn_outcome(monkeypatch):
    monkeypatch.setenv("LBG_PROXMOX_THIN_WARN_PCT", "85")
    monkeypatch.setenv("LBG_PROXMOX_THIN_CRIT_PCT", "95")
    stdout = "data_pct=89.55\nvg_free=16.00g\npvesm_local_lvm=89\nvm_prime_status=running\n"
    with patch("lbg_agents.proxmox_storage_probe._ssh_proxmox_host", return_value=(True, stdout, "")):
        payload = probe_proxmox_storage_host("192.168.0.201")
    assert payload["ok"] is True
    assert payload["outcome"] == "warn"
    assert payload["data_percent"] == 89.55
    assert "89.55" in format_storage_probe_reply(payload)


def test_probe_critical_io_error(monkeypatch):
    stdout = "data_pct=99\nvg_free=0\npvesm_local_lvm=99\nvm_prime_status=running(io-error)\n"
    with patch("lbg_agents.proxmox_storage_probe._ssh_proxmox_host", return_value=(True, stdout, "")):
        payload = probe_proxmox_storage_host("192.168.0.201")
    assert payload["outcome"] == "critical"


def test_probe_ssh_failure():
    with patch("lbg_agents.proxmox_storage_probe._ssh_proxmox_host", return_value=(False, "", "timeout")):
        payload = probe_proxmox_storage_host("192.168.0.201")
    assert payload["ok"] is False
    assert payload["outcome"] == "critical"


def test_multi_host_worst_outcome(monkeypatch):
    monkeypatch.setenv("LBG_PROXMOX_HOSTS", "192.168.0.201,192.168.0.202")
    ok_stdout = "data_pct=70\nvg_free=10g\npvesm_local_lvm=70\nvm_prime_status=running\n"
    warn_stdout = "data_pct=88\nvg_free=0\npvesm_local_lvm=88\nvm_prime_status=running\n"

    def fake_ssh(host, script, timeout_s=12.0):
        if host == "192.168.0.201":
            return True, warn_stdout, ""
        return True, ok_stdout, ""

    with patch("lbg_agents.proxmox_storage_probe._ssh_proxmox_host", side_effect=fake_ssh):
        payload = probe_proxmox_storage_local()
    assert payload["ok"] is True
    assert payload["outcome"] == "warn"
    assert payload["host"] == "192.168.0.201"
    assert len(payload["hosts"]) == 2
    reply = format_storage_probe_reply(payload)
    assert "192.168.0.201" in reply
    assert "192.168.0.202" in reply


def test_aggregate_all_failed():
    hosts = [
        {"ok": False, "outcome": "critical", "error": "timeout", "host": "192.168.0.201"},
        {"ok": False, "outcome": "critical", "error": "timeout", "host": "192.168.0.202"},
    ]
    agg = _aggregate_host_probes(hosts)
    assert agg["ok"] is False
    assert agg["outcome"] == "critical"


def test_storage_remediation_plan_warn():
    storage = {
        "ok": True,
        "outcome": "warn",
        "data_percent": 88.0,
        "host": "192.168.0.201",
        "vm246_status": "running",
        "vg_free": "10.00g",
        "hosts": [
            {"ok": True, "host": "192.168.0.201", "outcome": "warn", "data_percent": 88.0, "vg_free": "10.00g"},
        ],
    }
    plan = build_storage_remediation_plan(storage_payload=storage)
    assert plan["source"] == "proxmox_storage"
    assert plan["outcome"] == "warn"
    assert plan["suggested_actions"]
    assert any(a.get("devops_action") for a in plan["suggested_actions"] if isinstance(a, dict))


def test_thresholds_order(monkeypatch):
    monkeypatch.setenv("LBG_PROXMOX_THIN_WARN_PCT", "80")
    monkeypatch.setenv("LBG_PROXMOX_THIN_CRIT_PCT", "90")
    assert thin_warn_pct() == 80
    assert thin_crit_pct() == 90
