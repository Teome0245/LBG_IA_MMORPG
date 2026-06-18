"""Tests sonde Proxmox (devops kind proxmox_status)."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.proxmox_probe import run_proxmox_status


def test_skipped_when_not_configured():
    with patch("lbg_agents.proxmox_probe.proxmox_configured", return_value=False):
        out = run_proxmox_status(actor_id="sysops", text="état proxmox", context={})
    assert out["ok"] is True
    assert out["outcome"] == "skipped_not_configured"
    assert "LBG_PROXMOX_TOKEN" in out["reply"]


def test_warn_on_high_mem():
    fake_lan = {
        "ok": True,
        "matched": {
            "prime": {
                "vmid": 104,
                "status": {"ok": True, "status": {"status": "running", "mem_pct": 92.0, "cpu_pct": 40.0}},
            }
        },
    }
    with patch("lbg_agents.proxmox_probe.proxmox_configured", return_value=True):
        with patch("lbg_agents.proxmox_probe.get_cluster_status", return_value={"ok": True, "host": "200", "version": "8", "vm_count": 4}):
            with patch("lbg_agents.proxmox_probe.match_lan_vms", return_value=fake_lan):
                with patch("lbg_agents.proxmox_probe.list_vms", return_value={"ok": True, "count": 4}):
                    out = run_proxmox_status(actor_id="sysops", text="superviser proxmox", context={})
    assert out["outcome"] == "warn"
    assert out["alerts"]
