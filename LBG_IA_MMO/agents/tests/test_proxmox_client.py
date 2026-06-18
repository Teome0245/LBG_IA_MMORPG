"""Tests client Proxmox (mock HTTP)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx

from lbg_agents.proxmox_client import (
    _vm_summary,
    get_cluster_status,
    list_vms,
    proxmox_configured,
)


def test_proxmox_not_configured():
    with patch.dict("os.environ", {}, clear=True):
        assert proxmox_configured() is False
        out = get_cluster_status()
        assert out["ok"] is False
        assert out["error"] == "proxmox_not_configured"


def test_vm_summary_fields():
    row = {"vmid": 104, "name": "prime", "status": "running", "mem": 1, "maxmem": 10}
    s = _vm_summary(row)
    assert s["vmid"] == 104
    assert s["name"] == "prime"


def test_get_cluster_status_mock():
    version_body = {"data": {"version": "8.2.0", "release": "8.2"}}
    resources_body = {
        "data": [
            {"vmid": 101, "name": "core-orchestrateur", "status": "running", "node": "pve"},
        ]
    }

    def fake_request(self, method, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.content = b"{}"
        resp.status_code = 200
        if url.endswith("/version"):
            resp.json.return_value = version_body
        else:
            resp.json.return_value = resources_body
        return resp

    env = {
        "LBG_PROXMOX_TOKEN": "root@pam!t=secret",
        "LBG_PROXMOX_HOST": "192.168.0.200",
        "LBG_PROXMOX_VERIFY_SSL": "0",
    }
    with patch.dict("os.environ", env, clear=False):
        with patch.object(httpx.Client, "request", fake_request):
            out = get_cluster_status()
            assert out["ok"] is True
            assert out["version"] == "8.2.0"
            assert out["vm_count"] == 1
            listed = list_vms(running_only=True)
            assert listed["count"] == 1
