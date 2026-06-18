"""Tests watchdog infra (hors Prime)."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.infra_watchdog import run_infra_watchdog
from lbg_agents.vm_memory_probe import _probe_hosts


def test_probe_hosts_exclude_prime(monkeypatch):
    monkeypatch.setenv("LBG_INFRA_WATCHDOG_EXCLUDE_PRIME", "1")
    hosts = _probe_hosts()
    labels = {h[0] for h in hosts}
    assert "prime" not in labels
    assert "core" in labels
    assert "precu" in labels
    assert "front" in labels


def test_infra_watchdog_aggregates(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_INFRA_WATCHDOG_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LBG_INFRA_WATCHDOG_EXCLUDE_PRIME", "1")
    fake_mem = {
        "ok": True,
        "worst_status": "ok",
        "hosts": [],
        "reply": "mem ok",
    }
    fake_prox = {
        "ok": True,
        "outcome": "warn",
        "alerts": ["prime: RAM 92%"],
        "reply": "proxmox warn",
    }
    with patch("lbg_agents.infra_watchdog.proxmox_configured", return_value=True):
        with patch("lbg_agents.infra_watchdog.run_proxmox_status", return_value=fake_prox):
            with patch("lbg_agents.infra_watchdog.run_vm_memory_probe", return_value=fake_mem):
                out = run_infra_watchdog(actor_id="test")
    assert out["outcome"] == "warn"
    assert out["alerts"]
    assert (tmp_path / "state.json").is_file()


def test_infra_watchdog_skips_proxmox_without_token(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_INFRA_WATCHDOG_STATE", str(tmp_path / "state.json"))
    fake_mem = {"ok": True, "worst_status": "ok", "hosts": [], "reply": "mem"}
    with patch("lbg_agents.infra_watchdog.proxmox_configured", return_value=False):
        with patch("lbg_agents.infra_watchdog.run_vm_memory_probe", return_value=fake_mem):
            out = run_infra_watchdog(persist=False)
    assert out["proxmox"]["outcome"] == "skipped_not_configured"
    assert out["outcome"] == "ok"


def test_infra_watchdog_warn_includes_remediation_plan(monkeypatch, tmp_path):
    monkeypatch.setenv("LBG_INFRA_WATCHDOG_STATE", str(tmp_path / "state.json"))
    fake_mem = {
        "ok": True,
        "worst_status": "warn",
        "hosts": [
            {
                "label": "core",
                "host": "192.168.0.140",
                "ok": True,
                "status": "warn",
                "metrics": {"mem_avail_pct": 12.0, "top_processes": []},
            }
        ],
        "reply": "mem warn",
    }
    with patch("lbg_agents.infra_watchdog.proxmox_configured", return_value=False):
        with patch("lbg_agents.infra_watchdog.run_vm_memory_probe", return_value=fake_mem):
            out = run_infra_watchdog(persist=False)
    assert out["outcome"] == "warn"
    assert out["remediation_plan"]["kind"] == "remediation_plan"
    assert out["remediation_plan"]["stressed_hosts"]
